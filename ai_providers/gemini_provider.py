import os
import json
from typing import List, Dict, Any
import google.generativeai as Client

from ai_providers import AIProvider

class GeminiProvider(AIProvider):
    """Gemini AI provider implementation."""

    def __init__(self):
        self.model = None
        self.generation_config = {
            "max_output_tokens": 8192,
            "temperature": 0.8,
            "top_p": 0.95,
        }

    def configure(self) -> None:
        """Configure Gemini with API key and model."""
        Client.configure(api_key=os.environ.get('GEMINI_API_KEY'))
        model_name = os.environ.get('GEMINI_MODEL', 'gemini-2.0-flash-001')
        self.model = Client.GenerativeModel(model_name)

    def generate_review(self, prompt: str) -> List[Dict[str, Any]]:
        """Generate code review using Gemini AI."""
        try:
            response = self.model.generate_content(prompt, generation_config=self.generation_config)
            
            response_text = response.text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            try:
                data = json.loads(response_text)
                if "reviews" in data and isinstance(data["reviews"], list):
                    return [
                        review for review in data["reviews"]
                        if "lineNumber" in review and "reviewComment" in review
                    ]
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON response: {e}")
                return []
        except Exception as e:
            print(f"Error during Gemini API call: {e}")
            return []
        
        return []

    def get_name(self) -> str:
        """Get the provider name."""
        return "Gemini AI"