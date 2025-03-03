from typing import Dict, Type
from ai_providers import AIProvider
from ai_providers.gemini_provider import GeminiProvider
from ai_providers.deepseek_provider import DeepseekProvider

class AIProviderFactory:
    """Factory class for creating and managing AI providers."""
    
    _providers: Dict[str, Type[AIProvider]] = {
        'gemini': GeminiProvider,
        'deepseek': DeepseekProvider
    }

    @classmethod
    def get_provider(cls, provider_name: str) -> AIProvider:
        """Get an instance of the specified AI provider.
        
        Args:
            provider_name (str): Name of the provider to use ('gemini', 'deepseek', etc.)
            
        Returns:
            AIProvider: Configured instance of the specified provider
            
        Raises:
            ValueError: If the specified provider is not supported
        """
        provider_class = cls._providers.get(provider_name.lower())
        if not provider_class:
            supported = list(cls._providers.keys())
            raise ValueError(f"Unsupported AI provider: {provider_name}. Supported providers: {supported}")
        
        provider = provider_class()
        provider.configure()
        return provider

    @classmethod
    def register_provider(cls, name: str, provider_class: Type[AIProvider]) -> None:
        """Register a new AI provider.
        
        Args:
            name (str): Name to register the provider under
            provider_class (Type[AIProvider]): The provider class to register
        """
        cls._providers[name.lower()] = provider_class

    @classmethod
    def get_available_providers(cls) -> list[str]:
        """Get list of available provider names."""
        return list(cls._providers.keys())