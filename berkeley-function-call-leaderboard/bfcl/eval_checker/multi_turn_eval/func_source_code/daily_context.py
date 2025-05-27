import math
from typing import Dict, List, Optional, Any, Union
from concurrent.futures import Future, ThreadPoolExecutor
import uuid




'''DailyContext ASync Version (v2)'''
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
        self, location: str, time: str
    ) -> Dict[str, str]:
        fut = self._executor.submit(self._get_temperature_impl, location, time)
        # Create a unique ID
        fut_id = uuid.uuid4().hex
        self._registry[fut_id] = fut
        return {"future_id": fut_id}
        
    def _get_temperature_impl(self, location: str, time:str) -> Dict[str, float]:
        if (location not in ["Stanford", "Berkeley"]) or time not in ["9:00", "8:00"]:
            return {"error": "location or time in wrong format"}
        try:
            if (location=="Stanford" and time=="9:00"):
                result = 30.0
            elif (location=="Berkeley" and time=="8:00"):
                result = 20.0
            else:
                result = 40.4 # i.e. 404
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}
    
    # def get_temperature_future(self, future_id: str) -> Dict[str, float]:
    #     fut = self._registry.get(future_id)
    #     if fut is None:
    #         return {"error": "Unknown future_id"}
    #     try:
    #         result = fut.result()        # blocks until done
    #         return result                # e.g. {"result": 42}
    #     except Exception as e:
    #         return {"error": str(e)}
        
    def get_location(
            self, time: str
        ) -> Dict[str, str]:
            fut = self._executor.submit(self._get_location_impl, time)
            # Create a unique ID
            fut_id = uuid.uuid4().hex
            self._registry[fut_id] = fut
            return {"future_id": fut_id}
        
    def _get_location_impl(self, time:str) -> Dict[str, str]:
        try:
            if (time=="9:00"):
                result = "Stanford"
            elif (time=="8:00"):
                result = "Berkeley"
            else:
                return {"error": "location or time in wrong format"}
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}
    
    def get_future(self, future_id: str) -> Dict[str, Union[str, float]]:
        fut = self._registry.get(future_id)
        if fut is None:
            return {"error": "Unknown future_id"}
        try:
            result = fut.result()        # blocks until done
            return result                # e.g. {"result": 42}
        except Exception as e:
            return {"error": str(e)}
        
    # def get_location_future(self, future_id: str) -> Dict[str, str]:
    #     fut = self._registry.get(future_id)
    #     if fut is None:
    #         return {"error": "Unknown future_id"}
    #     try:
    #         result = fut.result()        # blocks until done
    #         return result                # e.g. {"result": 42}
    #     except Exception as e:
    #         return {"error": str(e)}
    
    def get_work_time(self, dummy: bool) -> Dict[str, str]:
        try:
            return {"result": "9:00"}
        except Exception as e:
            return {"error": str(e)}
        
    def get_current_time(self, dummy: bool) -> Dict[str, str]:
        try:
            return {"result": "8:00"}
        except Exception as e:
            return {"error": str(e)}
        
