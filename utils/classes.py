from typing import Any
from abc import ABC, abstractmethod


class Observer(ABC):
    """
    Abstract base class implementing the Observer pattern.
    
    This class serves as a base for all observer implementations.
    It defines the interface that must be implemented by concrete observers.
    """
    
    @abstractmethod
    async def notify(self, notification: Any) -> Any:
        """
        Asynchronously notifies the observer about some events.
        
        Args:
            notification: some notification object.
            
        Returns:
            Any: The result of the notification processing.
            
        Raises:
            NotImplementedError: If the method is not overridden in a subclass.
        """
        pass

    @property
    def name(self) -> str:
        """
        Returns the name of the observer class.
        
        Returns:
            str: The name of the observer class.
        """
        return type(self).__name__