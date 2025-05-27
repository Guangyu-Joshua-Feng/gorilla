import math
from typing import Dict, List, Optional, Union
from concurrent.futures import Future, ThreadPoolExecutor
import uuid




'''DailyContext ASync Version (v1)'''
class DailyContext:
    def __init__(self):
        self._api_description = "DailyContext provides contextual information relevant to a user's daily routine."
        
        if not hasattr(self, "_executor"):
            # A thread pool for running sync work in the background
            self._executor = ThreadPoolExecutor()
        if not hasattr(self, "_registry"):
            # Global future registry
            self._registry: dict[str, Future] = {}

    def get_temperature(
        self, location: str
    ) -> Dict[str, str]:
        fut = self._executor.submit(self._get_temperature_impl, location)
        # Create a unique ID
        fut_id = uuid.uuid4().hex
        self._registry[fut_id] = fut
        return {"future_id": fut_id}
        
    def _get_temperature_impl(self, location: str) -> Dict[str, float]:
        try:
            if (location=="Stanford"):
                result = 30.0
            else:
                result = 20.0

            return {"result": result}
        except Exception as e:
            return {"error": str(e)}
    
    def eval_future(self, future_id: str) -> Dict[str, float]:
        fut = self._registry.get(future_id)
        if fut is None:
            return {"error": "Unknown future_id"}
        try:
            result = fut.result()        # blocks until done
            return result                # e.g. {"result": 42}
        except Exception as e:
            return {"error": str(e)}

    def subtract(self, a: float, b: float) -> Dict[str, float]:
        """
        Subtract one number from another.

        Args:
            a (float): Number to subtract from.
            b (float): Number to subtract.

        Returns:
            result (float): Difference between the two numbers.
        """
        try:
            return {"result": a - b}
        except TypeError:
            return {"error": "Both inputs must be numbers"}

# '''DailyContext sync Version'''
# class DailyContext:
#     def __init__(self):
#         self._api_description = "DailyContext provides contextual information relevant to a user's daily routine."
        
#     def get_temperature(
#         self, location: str
#     ) -> Dict[str, float]:
        
#         try:
#             if (location=="Stanford"):
#                 result = 30.0
#             else:
#                 result = 20.0

#             return {"result": result}
#         except Exception as e:
#             return {"error": str(e)}

#     def subtract(self, a: float, b: float) -> Dict[str, float]:
#         """
#         Subtract one number from another.

#         Args:
#             a (float): Number to subtract from.
#             b (float): Number to subtract.

#         Returns:
#             result (float): Difference between the two numbers.
#         """
#         try:
#             return {"result": a - b}
#         except TypeError:
#             return {"error": "Both inputs must be numbers"}
