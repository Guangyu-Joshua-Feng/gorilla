# Custom FC: Single-Step to Multi-Turn Testing

Author: [@Guangyu-Joshua-Feng](https://github.com/Guangyu-Joshua-Feng)

This branch allows users to test their own custom prompts and function documentation against various API-based LLM models **Single-step** through **Multi-turn Multi-step** scenarios, similar to the testing workflow covered in BFCL v1–v3. Users can plug in their own function definitions, implementations, and prompts to evaluate different API-based LLM models.

---

## Multi-turn(Step) Testing Setup (eg: BFCL v3)

1. **Function Documentation:**  
   Place your custom function doc in:
    `berkeley-function-call-leaderboard/data/multi_turn_func_doc/daily_context.json`

2. **Function Implementation:**  
Implement the functions in:
`berkeley-function-call-leaderboard/bfcl/eval_checker/multi_turn_eval/func_source_code/daily_context.py`

3. **Prompt File:**  
Add your test prompts to:
`berkeley-function-call-leaderboard/data/BFCL_v3_multi_turn_custom.json`

4. **Run via VSCode debugger:**
Add this configuration in `.vscode/launch.json`:
```json
{
    "name": "Debug bfcl gemini-2.5-0506 generate multiturn async",
    "type": "debugpy",
    "request": "launch",
    "module": "bfcl",
    "args": [
        "generate",
        "--model", "gemini-2.5-pro-preview-05-06-FC",
        "--test-category", "multi_turn_custom"
    ],
    "console": "integratedTerminal"
}
```

5. **Run Directly in Terminal:**

`bfcl generate --model gemini-2.5-pro-preview-05-06-FC --test-category multi_turn_custom`


## Single-turn Single Step Testing Setup (eg: BFCL v1 and v2)

1. **Prompt and function call description:**
Add content to:
`berkeley-function-call-leaderboard/data/BFCL_v3_custom.json`

2. **Run via VSCode debugger:**
Add this configuration in `.vscode/launch.json`:
```json
{
    "name": "Debug bfcl gemini-2.0-FC generate custom",
    "type": "debugpy",
    "request": "launch",
    "module": "bfcl",
    "args": [
        "generate",
        "--model", "gemini-2.0-flash-001-FC",
        "--test-category", "custom"
    ],
    "console": "integratedTerminal"
}
```

3. **Run Directly in Terminal:**
`bfcl generate --model gemini-2.0-flash-001-FC --test-category custom`


---

## Execution Notes
Before execution,
1. Conda activate BFCL
2. Convert every JSON object to one line using Ctrl + J (Join lines).
3. Delete previous result files from: `berkeley-function-call-leaderboard/result/<model_name>/`

After Execution 
1. Reformat JSON outputs for readability using Option + Shift + F (macOS) or equivalent formatting shortcut.