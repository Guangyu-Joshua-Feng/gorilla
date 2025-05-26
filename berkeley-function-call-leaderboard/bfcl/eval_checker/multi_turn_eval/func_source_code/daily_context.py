import math
from typing import Dict, List, Optional, Union



class DailyContext:
    def __init__(self):
        self._api_description = "DailyContext provides contextual information relevant to a user's daily routine."
        
    def get_temperature(
        self, location: str
    ) -> Dict[str, float]:
        
        try:
            if (location=="Stanford"):
                result = 30.0
            else:
                result = 20.0

            return {"result": result}
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
