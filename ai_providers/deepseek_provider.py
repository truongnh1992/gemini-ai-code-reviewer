import os
import json
from typing import List, Dict, Any
import requests

from ai_providers import AIProvider

class DeepseekProvider(AIProvider):
    """Deepseek AI provider implementation."""

    def __init__(self):
        self.api_url = "https://api.deepseek.com/chat/completions"
        self.api_key = None
        self.model = None
        self.config = {
            "temperature": 0.8,
            "max_tokens": 8192,
            "stream": False
        }

    def configure(self) -> None:
        """Configure Deepseek with API key and model."""
        self.api_key = os.environ.get('DEEPSEEK_API_KEY')
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable is required")
        self.model = os.environ.get('DEEPSEEK_MODEL', 'deepseek-chat')

    def generate_review(self, prompt: str) -> List[Dict[str, Any]]:
        """Generate code review using Deepseek AI."""
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }

            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are an expert code reviewer. Provide detailed, constructive feedback in JSON format."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": self.config["temperature"],
                "max_tokens": self.config["max_tokens"],
                "stream": self.config["stream"]
            }

            response = requests.post(self.api_url, headers=headers, json=data)
            
            if not response.ok:
                error_msg = f"{response.status_code} {response.reason}"
                try:
                    error_data = response.json()
                    if 'error' in error_data:
                        error_msg += f": {error_data['error'].get('message', '')}"
                except:
                    pass
                print(f"Deepseek API error: {error_msg}")
                return []
            
            response_data = response.json()
            print(f"API Response Body: {response_data}")

            response_text = response_data['choices'][0]['message']['content'].strip()

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
            print(f"Error during Deepseek API call: {e}")
            return []
        
        return []

    def get_name(self) -> str:
        """Get the provider name."""
        return "Deepseek AI"