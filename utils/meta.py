import asyncio
from types import FunctionType

from exceptions import MonitoringSystemException
from utils.log import get_logger

class ExceptionHandlingMeta(type):
    """
    Metaclass that automatically wraps all class methods (excluding `__init__`) with exception handling.
    
    Automatically adds try-except blocks to all methods of the class, logging errors
    and handling MonitoringSystemException specifically.
    """
    def __new__(cls, name: str, bases: tuple, dct: dict) -> type:
        """
        Creates a new class with wrapped methods.
        
        Args:
            name (str): Name of the class being created.
            bases (tuple): Tuple of base classes.
            dct (dict): Dictionary containing class attributes and methods.
            
        Returns:
            type: New class with wrapped methods.
        """
        logger = get_logger(name)
        def create_wrapper(original_method: FunctionType, is_async: bool) -> FunctionType:
            """
            Creates a wrapper function for the original method.
            
            Args:
                original_method (FunctionType): Original method to wrap.
                is_async (bool): Flag indicating if the method is async.
                
            Returns:
                FunctionType: Wrapped method with exception handling.
            """
            if is_async:
                async def wrapper(*args, **kwargs):
                    """
                    Asynchronous wrapper for method execution.
                    
                    Handles exceptions and logs errors.
                    """
                    try:
                        return await original_method(*args, **kwargs)
                    except MonitoringSystemException as exc:
                        raise exc from exc
                    except Exception:
                        logger.error("An error has occurred in method %s:", original_method.__name__, exc_info=True)
                        return
            else:
                def wrapper(*args, **kwargs):
                    """
                    Synchronous wrapper for method execution.
                    
                    Handles exceptions and logs errors.
                    """
                    try:
                        return original_method(*args, **kwargs)
                    except MonitoringSystemException as exc:
                        raise exc from exc
                    except Exception:
                        logger.error("An error has occurred in method %s:", original_method.__name__, exc_info=True)
                        return
            return wrapper
        
        for attr_name, attr_value in dct.items():
            if isinstance(attr_value, FunctionType) and attr_name != "__init__":
                is_async = asyncio.iscoroutinefunction(attr_value)
                dct[attr_name] = create_wrapper(attr_value, is_async)
        
        return super().__new__(cls, name, bases, dct)
