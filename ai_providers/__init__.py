from abc import ABC, abstractmethod
from typing import List, Dict, Any

class AIProvider(ABC):
    """Abstract base class for AI code review providers."""
    
    @abstractmethod
    def configure(self) -> None:
        """Configure the AI provider with necessary credentials and settings."""
        pass

    @abstractmethod
    def generate_review(self, prompt: str) -> List[Dict[str, Any]]:
        """Generate code review from the given prompt.
        
        Args:
            prompt (str): The code review prompt
            
        Returns:
            List[Dict[str, Any]]: List of review comments in the format:
            [{"lineNumber": int, "reviewComment": str}]
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Get the name of the AI provider."""
        pass