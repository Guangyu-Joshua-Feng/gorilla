import os
import time

import vertexai
from bfcl.constants.type_mappings import GORILLA_TO_OPENAPI
from bfcl.model_handler.base_handler import BaseHandler
from bfcl.model_handler.model_style import ModelStyle
from bfcl.model_handler.utils import (
    convert_to_tool,
    default_decode_ast_prompting,
    default_decode_execute_prompting,
    extract_system_prompt,
    format_execution_results_prompting,
    func_doc_language_specific_pre_processing,
    retry_with_backoff,
    system_prompt_pre_processing_chat_model,
)
from google.api_core.exceptions import ResourceExhausted, TooManyRequests
from vertexai.generative_models import (
    Content,
    FunctionDeclaration,
    GenerationConfig,
    GenerativeModel,
    Part,
    Tool,
)

# Google Uses Vertex AI to manage its API calls. 
class GeminiHandler(BaseHandler):
    def __init__(self, model_name, temperature) -> None:
        super().__init__(model_name, temperature)
        self.model_style = ModelStyle.Google
        # Initialize Vertex AI
        vertexai.init(
            project=os.getenv("VERTEX_AI_PROJECT_ID"),
            location=os.getenv("VERTEX_AI_LOCATION"),
        )
        self.client = GenerativeModel(self.model_name.replace("-FC", "")) # Create a model using the bare-bone model name.

    '''
    Vertex AI expects roles user, model, and function (not assistant or tool), so this helper remaps them in the prompt accordingly
    '''
    @staticmethod
    def _substitute_prompt_role(prompts: list[dict]) -> list[dict]:
        # Allowed roles: user, model, function
        for prompt in prompts:
            if prompt["role"] == "user":
                prompt["role"] = "user"
            elif prompt["role"] == "assistant":
                prompt["role"] = "model"
            elif prompt["role"] == "tool":
                prompt["role"] = "function"

        return prompts

    def decode_ast(self, result, language="Python"):
        if "FC" not in self.model_name:
            result = result.replace("```tool_code\n", "").replace("\n```", "")
            return default_decode_ast_prompting(result, language)
        else:
            if type(result) is not list:
                result = [result]
            return result

    
    def decode_execute(self, result):
        if "FC" not in self.model_name:
            result = result.replace("```tool_code\n", "").replace("\n```", "")
            return default_decode_execute_prompting(result)
        else: # for FC models, builds a list of function-call strings like foo(a=1,b='x')
            func_call_list = []
            for function_call in result:
                for func_name, func_args in function_call.items():
                    func_call_list.append(
                        f"{func_name}({','.join([f'{k}={repr(v)}' for k, v in func_args.items()])})"
                    )
            return func_call_list

    @retry_with_backoff(error_type=[ResourceExhausted, TooManyRequests])
    def generate_with_backoff(self, client, **kwargs):
        start_time = time.time()
        api_response = client.generate_content(**kwargs)
        end_time = time.time()

        return api_response, end_time - start_time

    #### FC methods ####

    '''
    FC Pipeline #3: 
    Call Model API
        - Extract all the tools from the inference_data object so they will be passed into the model call later
        - Generate inference_data["inference_input_log"] from other fields of the object to log the data (not passed into model)
        - Reinitialize model if user input involves system prompts. 
        - add model, msg, config, and tools into the API model inference call
    '''
    def _query_FC(self, inference_data: dict):
        # Gemini models needs to first conver the function doc to FunctionDeclaration and Tools objects.
        # We do it here to avoid json serialization issues.
        func_declarations = []
        for function in inference_data["tools"]:
            func_declarations.append(
                FunctionDeclaration(
                    name=function["name"],
                    description=function["description"],
                    parameters=function["parameters"],
                )
            )

        if func_declarations:
            tools = [Tool(function_declarations=func_declarations)]
        else:
            tools = None

        inference_data["inference_input_log"] = {
            "message": repr(inference_data["message"]),
            "tools": inference_data["tools"],
            "system_prompt": inference_data.get("system_prompt", None),
        }

        # messages are already converted to Content object
        if "system_prompt" in inference_data:
            # We re-instantiate the GenerativeModel object with the system prompt
            # We cannot reassign the self.client object as it will affect other entries
            client = GenerativeModel(
                self.model_name.replace("-FC", ""),
                system_instruction=inference_data["system_prompt"],
            )
        else:
            client = self.client

        return self.generate_with_backoff(
            client=client,
            contents=inference_data["message"],
            generation_config=GenerationConfig(
                temperature=self.temperature,
            ),
            tools=tools,
        )

    '''
    FC pipeline #1: 
    Preprocess the testset entry before sending it to the model. 
    inference_data dictionary serves as a centralized data structure that accumulates and manages all necessary information throughout the model inference process.

    Steps: 
    - Update prompt's roles in Json.
    - Extracts any system prompt from the first user message.
    - Initializes an empty message list.
    '''
    def _pre_query_processing_FC(self, inference_data: dict, test_entry: dict) -> dict:

        for round_idx in range(len(test_entry["question"])):
            test_entry["question"][round_idx] = self._substitute_prompt_role(
                test_entry["question"][round_idx]
            )

        inference_data["message"] = []

        system_prompt = extract_system_prompt(test_entry["question"][0])
        if system_prompt:
            inference_data["system_prompt"] = system_prompt
        return inference_data

    '''
    FC-pipeline #2
    Prepare Functions in testing Prompts into the form acceptable by models. 
    Steps:
        - Convert Functions into format based on language
        - Oncert functions into format based on the model provider. 
        - Add tools info into inference_data object. 
    '''
    def _compile_tools(self, inference_data: dict, test_entry: dict) -> dict:
        functions: list = test_entry["function"]
        test_category: str = test_entry["id"].rsplit("_", 1)[0]

        functions = func_doc_language_specific_pre_processing(functions, test_category)
        tools = convert_to_tool(functions, GORILLA_TO_OPENAPI, self.model_style)

        inference_data["tools"] = tools

        return inference_data

    '''
    FC-Pipeline Step #4:
        - Parse the json response into function name with arguments, just function names, and just text
        Input of Json API Response: 
        [
            { "function_call": { "name": "get_weather", "args": {"city": "Seattle"} } },
            { "text": "Here’s what I found." }
        ]
        Output of the Parsed result: 
        fc_parts = [{"get_weather": {"city": "Seattle"}}]
        tool_call_func_names = ["get_weather"]
        text_parts = ["Here’s what I found."]
        The output will be wrapped into forming the return objects. 
    '''
    def _parse_query_response_FC(self, api_response: any) -> dict:
        tool_call_func_names = [] # tracks just the function names (e.g., ["get_weather"])
        fc_parts = [] # a list of { function name: function args } mappings
        text_parts = [] # the text of the return value

        if (
            len(api_response.candidates) > 0
            and len(api_response.candidates[0].content.parts) > 0
        ):  
            # Select only the best model response
            response_function_call_content = api_response.candidates[0].content


            for part in api_response.candidates[0].content.parts:
                # part.function_call is a FunctionCall object, so it will always be True even if it contains no function call
                # So we need to check if the function name is empty `""` to determine if Gemini returned a function call
                if part.function_call and part.function_call.name:
                    part_func_name = part.function_call.name
                    part_func_args = part.function_call.args
                    part_func_args_dict = {k: v for k, v in part_func_args.items()}

                    fc_parts.append({part_func_name: part_func_args_dict})
                    tool_call_func_names.append(part_func_name)
                else:
                    text_parts.append(part.text)
        else:
            response_function_call_content = Content(
                role="model",
                parts=[
                    Part.from_text("The model did not return any response."),
                ],
            )

        model_responses = fc_parts if fc_parts else text_parts

        return {
            "model_responses": model_responses, # function along with argument (if function exists), otherwise just text resposne
            "model_responses_message_for_chat_history": response_function_call_content, # whole API best resonsse
            "tool_call_func_names": tool_call_func_names, # just functio names
            "input_token": api_response.usage_metadata.prompt_token_count, # number of token
            "output_token": api_response.usage_metadata.candidates_token_count, # # number of token
        }
    '''
    FC-Pipeline Step #5: Multi-turn context update
    These methods below simply append the right kind of Content(...) to inference_data["message"] at each step
    '''

    '''
    Add a user’s JSON message of the turn into a inference_data["message"]
    '''
    def add_first_turn_message_FC(
        self, inference_data: dict, first_turn_message: list[dict]
    ) -> dict:
        for message in first_turn_message:
            inference_data["message"].append(
                Content(
                    role=message["role"],
                    parts=[
                        Part.from_text(message["content"]),
                    ],
                )
            )
        return inference_data

    '''
    Add a user’s JSON message of the turn into a inference_data["message"]
    '''
    def _add_next_turn_user_message_FC(
        self, inference_data: dict, user_message: list[dict]
    ) -> dict:
        return self.add_first_turn_message_FC(inference_data, user_message)

    def _add_assistant_message_FC(
        self, inference_data: dict, model_response_data: dict
    ) -> dict:
        inference_data["message"].append(
            model_response_data["model_responses_message_for_chat_history"]
        )
        return inference_data
    '''
    Add the execution results to the chat history to prepare for the next turn of query.
    '''
    def _add_execution_results_FC(
        self,
        inference_data: dict,
        execution_results: list[str],
        model_response_data: dict,
    ) -> dict:
        # Tool response needs to be converted to Content object as well.
        # One Content object for all tool responses.
        tool_response_parts = []
        for execution_result, tool_call_func_name in zip(
            execution_results, model_response_data["tool_call_func_names"]
        ):
            tool_response_parts.append(
                Part.from_function_response(
                    name=tool_call_func_name,
                    response={
                        "content": execution_result,
                    },
                )
            )

        tool_response_content = Content(parts=tool_response_parts)
        inference_data["message"].append(tool_response_content)

        return inference_data

    #### Prompting methods ####

    def _query_prompting(self, inference_data: dict):
        inference_data["inference_input_log"] = {
            "message": repr(inference_data["message"]),
            "system_prompt": inference_data.get("system_prompt", None),
        }

        # messages are already converted to Content object
        if "system_prompt" in inference_data:
            client = GenerativeModel(
                self.model_name.replace("-FC", ""),
                system_instruction=inference_data["system_prompt"],
            )
        else:
            client = self.client
        api_response = self.generate_with_backoff(
            client=client,
            contents=inference_data["message"],
            generation_config=GenerationConfig(
                temperature=self.temperature,
            ),
        )
        return api_response

    def _pre_query_processing_prompting(self, test_entry: dict) -> dict:
        functions: list = test_entry["function"]
        test_category: str = test_entry["id"].rsplit("_", 1)[0]

        functions = func_doc_language_specific_pre_processing(functions, test_category)

        for round_idx in range(len(test_entry["question"])):
            test_entry["question"][round_idx] = self._substitute_prompt_role(
                test_entry["question"][round_idx]
            )

        test_entry["question"][0] = system_prompt_pre_processing_chat_model(
            test_entry["question"][0], functions, test_category
        )
        # Gemini has system prompt in a specific field
        system_prompt = extract_system_prompt(test_entry["question"][0])

        if system_prompt:
            return {"message": [], "system_prompt": system_prompt}
        else:
            return {"message": []}

    def _parse_query_response_prompting(self, api_response: any) -> dict:
        if (
            len(api_response.candidates) > 0
            and len(api_response.candidates[0].content.parts) > 0
        ):
            model_responses = api_response.text
        else:
            model_responses = "The model did not return any response."
        return {
            "model_responses": model_responses,
            "input_token": api_response.usage_metadata.prompt_token_count,
            "output_token": api_response.usage_metadata.candidates_token_count,
        }

    def add_first_turn_message_prompting(
        self, inference_data: dict, first_turn_message: list[dict]
    ) -> dict:
        for message in first_turn_message:
            inference_data["message"].append(
                Content(
                    role=message["role"],
                    parts=[
                        Part.from_text(message["content"]),
                    ],
                )
            )
        return inference_data

    def _add_next_turn_user_message_prompting(
        self, inference_data: dict, user_message: list[dict]
    ) -> dict:
        return self.add_first_turn_message_prompting(inference_data, user_message)

    '''
    Adding model generated text into the model context
    '''
    def _add_assistant_message_prompting(
        self, inference_data: dict, model_response_data: dict
    ) -> dict:
        inference_data["message"].append(
            Content(
                role="model",
                parts=[
                    Part.from_text(model_response_data["model_responses"]),
                ],
            )
        )
        return inference_data

    '''
    Adding tool execution result into the model context
    '''
    def _add_execution_results_prompting(
        self, inference_data: dict, execution_results: list[str], model_response_data: dict
    ) -> dict:
        formatted_results_message = format_execution_results_prompting(
            inference_data, execution_results, model_response_data
        )
        tool_message = Content(
            role="user",
            parts=[
                Part.from_text(formatted_results_message),
            ],
        )
        inference_data["message"].append(tool_message)
        return inference_data
