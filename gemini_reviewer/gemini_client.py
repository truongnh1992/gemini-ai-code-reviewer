"""
Gemini AI client for the Gemini AI Code Reviewer.

This module handles all interactions with Google's Gemini AI including
prompt engineering, response validation, and error handling.
"""

import json
import logging
import time
from typing import List, Dict, Any, Optional
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .config import GeminiConfig, ReviewMode
from .models import AIResponse, ReviewPriority, AnalysisContext, HunkInfo, PRDetails


logger = logging.getLogger(__name__)


class GeminiClientError(Exception):
    """Base exception for Gemini client errors."""
    pass


class ModelNotAvailableError(GeminiClientError):
    """Exception raised when the specified model is not available."""
    pass


class TokenLimitExceededError(GeminiClientError):
    """Exception raised when token limit is exceeded."""
    pass


class GeminiClient:
    """Gemini AI client with retry logic and comprehensive error handling."""
    
    def __init__(self, config: GeminiConfig):
        """Initialize Gemini client with configuration."""
        self.config = config
        
        try:
            genai.configure(api_key=config.api_key)
            self._model = genai.GenerativeModel(config.model_name)
            logger.info(f"Initialized Gemini client with model: {config.model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {str(e)}")
            raise GeminiClientError(f"Failed to initialize Gemini client: {str(e)}")
        
        self._generation_config = {
            "max_output_tokens": config.max_output_tokens,
            "temperature": config.temperature,
            "top_p": config.top_p,
        }
        
        # Statistics tracking
        self._total_requests = 0
        self._successful_requests = 0
        self._failed_requests = 0
        self._total_tokens_used = 0
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type((Exception,))
    )
    def analyze_code_hunk(
        self,
        hunk: HunkInfo,
        context: AnalysisContext,
        prompt_template: str
    ) -> List[AIResponse]:
        """Analyze a code hunk and return AI responses with retry logic."""
        self._total_requests += 1
        
        if not hunk or not hunk.content:
            logger.warning("Empty hunk provided for analysis")
            return []
        
        if not context or not context.pr_details:
            logger.warning("Invalid analysis context provided")
            return []
        
        try:
            prompt = self._create_analysis_prompt(hunk, context, prompt_template)
            
            if len(prompt) > self.config.max_prompt_length:
                logger.warning(f"Prompt too long ({len(prompt)} chars), truncating...")
                prompt = prompt[:self.config.max_prompt_length] + "...[truncated]"
            
            logger.debug(f"Analyzing hunk with {len(hunk.content)} characters of content")
            logger.debug(f"Prompt preview: {prompt[:200]}...")
            
            response = self._generate_content_with_validation(prompt)
            ai_responses = self._parse_ai_response(response)
            
            self._successful_requests += 1
            logger.info(f"Generated {len(ai_responses)} AI responses for hunk")
            
            return ai_responses
            
        except Exception as e:
            self._failed_requests += 1
            logger.error(f"Error analyzing code hunk: {str(e)}")
            raise
    
    def _generate_content_with_validation(self, prompt: str) -> str:
        """Generate content with validation and error handling."""
        logger.info("Sending request to Gemini API...")
        
        try:
            response = self._model.generate_content(prompt, generation_config=self._generation_config)
            
            if not response or not hasattr(response, 'text'):
                raise GeminiClientError("Empty or invalid response from Gemini API")
            
            response_text = response.text.strip()
            if not response_text:
                raise GeminiClientError("Empty response text from Gemini API")
            
            logger.debug(f"Received response (length: {len(response_text)})")
            
            # Track token usage if available
            if hasattr(response, 'usage_metadata'):
                try:
                    tokens_used = response.usage_metadata.total_token_count
                    self._total_tokens_used += tokens_used
                    logger.debug(f"Tokens used: {tokens_used}")
                except Exception:
                    pass  # Token counting not critical
            
            return response_text
            
        except Exception as e:
            error_msg = str(e).lower()
            
            if "quota" in error_msg or "rate limit" in error_msg:
                logger.warning("Gemini API rate limit or quota exceeded")
                raise GeminiClientError("API rate limit exceeded")
            elif "not found" in error_msg or "model" in error_msg:
                raise ModelNotAvailableError(f"Model {self.config.model_name} not available")
            elif "token" in error_msg and "limit" in error_msg:
                raise TokenLimitExceededError("Token limit exceeded")
            else:
                logger.error(f"Gemini API error: {str(e)}")
                raise GeminiClientError(f"Gemini API error: {str(e)}")
    
    def _create_analysis_prompt(
        self,
        hunk: HunkInfo,
        context: AnalysisContext,
        prompt_template: str
    ) -> str:
        """Create a comprehensive analysis prompt."""
        # Sanitize inputs
        sanitized_content = self._sanitize_code_content(hunk.content)
        sanitized_title = self._sanitize_text(context.pr_details.title)
        sanitized_description = self._sanitize_text(context.pr_details.description or "No description provided")
        
        # Add context information
        context_info = []
        if context.file_info:
            context_info.append(f"File: {context.file_info.path}")
            if context.file_info.file_extension:
                context_info.append(f"Language: {self._detect_language(context.file_info.file_extension)}")
        
        if context.is_test_file:
            context_info.append("Note: This is a test file")
        
        if context.related_files:
            context_info.append(f"Related files: {', '.join(context.related_files[:3])}")
        
        context_string = "\n".join(context_info) if context_info else ""
        
        # Build the complete prompt
        prompt_parts = [
            prompt_template,
            "",
            f"Pull request title: {sanitized_title}",
            "Pull request description:",
            "---",
            sanitized_description,
            "---",
            ""
        ]
        
        if context_string:
            prompt_parts.extend([
                "Context:",
                context_string,
                ""
            ])
        
        prompt_parts.extend([
            "Git diff to review:",
            "```diff",
            sanitized_content,
            "```"
        ])
        
        return "\n".join(prompt_parts)
    
    def _parse_ai_response(self, response_text: str) -> List[AIResponse]:
        """Parse AI response and validate the structure."""
        try:
            # Clean the response text
            cleaned_response = self._clean_response_text(response_text)
            logger.debug(f"Cleaned response preview: {cleaned_response[:200]}...")
            
            # Parse JSON
            data = json.loads(cleaned_response)
            logger.debug("Successfully parsed JSON response from Gemini")
            
            if not isinstance(data, dict) or "reviews" not in data:
                logger.warning("Response doesn't contain 'reviews' field")
                return []
            
            reviews = data.get("reviews", [])
            if not isinstance(reviews, list):
                logger.warning("Reviews field is not a list")
                return []
            
            # Convert to AIResponse objects
            ai_responses = []
            for review in reviews:
                ai_response = self._parse_single_review(review)
                if ai_response:
                    ai_responses.append(ai_response)
            
            logger.info(f"Successfully parsed {len(ai_responses)} AI responses")
            return ai_responses
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {str(e)}")
            logger.debug(f"Raw response: {response_text[:1000]}...")
            return []
        except Exception as e:
            logger.error(f"Error parsing AI response: {str(e)}")
            return []
    
    def _parse_single_review(self, review: Dict[str, Any]) -> Optional[AIResponse]:
        """Parse a single review from the AI response."""
        try:
            if not isinstance(review, dict):
                logger.warning(f"Invalid review format: {type(review)}")
                return None
            
            # Validate required fields
            if "lineNumber" not in review or "reviewComment" not in review:
                logger.warning(f"Review missing required fields: {review}")
                return None
            
            # Parse and validate line number
            try:
                line_number = int(review["lineNumber"])
                if line_number <= 0:
                    logger.warning(f"Invalid line number: {line_number}")
                    return None
            except (ValueError, TypeError):
                logger.warning(f"Invalid line number format: {review.get('lineNumber')}")
                return None
            
            # Get and sanitize comment
            comment = self._sanitize_text(str(review["reviewComment"]))
            if not comment or len(comment.strip()) == 0:
                logger.warning("Empty review comment")
                return None
            
            # Parse optional fields
            priority = self._parse_priority(review.get("priority"))
            category = review.get("category")
            confidence = self._parse_confidence(review.get("confidence"))
            
            return AIResponse(
                line_number=line_number,
                review_comment=comment,
                priority=priority,
                category=category,
                confidence=confidence
            )
            
        except Exception as e:
            logger.warning(f"Error parsing single review: {str(e)}")
            return None
    
    def _clean_response_text(self, response_text: str) -> str:
        """Clean the response text from common formatting issues."""
        cleaned = response_text.strip()
        
        # Remove markdown code block markers
        if cleaned.startswith('```json'):
            cleaned = cleaned[7:]
        elif cleaned.startswith('```'):
            cleaned = cleaned[3:]
        
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]
        
        return cleaned.strip()
    
    def _parse_priority(self, priority_value: Any) -> ReviewPriority:
        """Parse priority from AI response."""
        if not priority_value:
            return ReviewPriority.MEDIUM
        
        try:
            priority_str = str(priority_value).lower()
            priority_mapping = {
                'critical': ReviewPriority.CRITICAL,
                'high': ReviewPriority.HIGH,
                'medium': ReviewPriority.MEDIUM,
                'low': ReviewPriority.LOW
            }
            return priority_mapping.get(priority_str, ReviewPriority.MEDIUM)
        except Exception:
            return ReviewPriority.MEDIUM
    
    def _parse_confidence(self, confidence_value: Any) -> Optional[float]:
        """Parse confidence score from AI response."""
        if confidence_value is None:
            return None
        
        try:
            confidence = float(confidence_value)
            return max(0.0, min(1.0, confidence))  # Clamp to [0, 1]
        except (ValueError, TypeError):
            return None
    
    def _detect_language(self, file_extension: str) -> str:
        """Detect programming language from file extension."""
        language_mapping = {
            'py': 'Python', 'js': 'JavaScript', 'ts': 'TypeScript',
            'java': 'Java', 'cpp': 'C++', 'c': 'C', 'cs': 'C#',
            'go': 'Go', 'rs': 'Rust', 'php': 'PHP', 'rb': 'Ruby',
            'swift': 'Swift', 'kt': 'Kotlin', 'scala': 'Scala',
            'html': 'HTML', 'css': 'CSS', 'scss': 'SCSS', 'sass': 'SASS',
            'xml': 'XML', 'json': 'JSON', 'yaml': 'YAML', 'yml': 'YAML',
            'sql': 'SQL', 'sh': 'Shell', 'bash': 'Bash', 'ps1': 'PowerShell'
        }
        return language_mapping.get(file_extension.lower(), 'Unknown')
    
    @staticmethod
    def _sanitize_text(text: str) -> str:
        """Sanitize text input to prevent injection attacks."""
        if not isinstance(text, str):
            return str(text) if text is not None else ""
        
        import html
        # HTML escape to prevent XSS
        sanitized = html.escape(text)
        
        # Remove potential command injection characters
        dangerous_chars = ['`', '$', '$(', '${', '|', '&&', '||', ';', '&']
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '')
        
        return sanitized.strip()
    
    @staticmethod
    def _sanitize_code_content(content: str) -> str:
        """Sanitize code content while preserving structure."""
        if not isinstance(content, str):
            return str(content) if content is not None else ""
        
        # For code content, we're more lenient but still remove obvious injection attempts
        lines = content.split('\n')
        sanitized_lines = []
        
        for line in lines:
            # Remove null bytes and control characters but keep normal code characters
            sanitized_line = ''.join(char for char in line if ord(char) >= 32 or char in '\t\n\r')
            sanitized_lines.append(sanitized_line)
        
        return '\n'.join(sanitized_lines)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get client usage statistics."""
        success_rate = 0.0
        if self._total_requests > 0:
            success_rate = self._successful_requests / self._total_requests
        
        return {
            'total_requests': self._total_requests,
            'successful_requests': self._successful_requests,
            'failed_requests': self._failed_requests,
            'success_rate': success_rate,
            'total_tokens_used': self._total_tokens_used,
            'model_name': self.config.model_name
        }
    
    def test_connection(self) -> bool:
        """Test connection to Gemini API."""
        try:
            test_prompt = "Respond with 'OK' if you can read this message."
            response = self._model.generate_content(test_prompt)
            return response and hasattr(response, 'text') and response.text.strip()
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return False
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for a text (rough approximation)."""
        # Rough approximation: 1 token ≈ 4 characters for English text
        # This is just an estimate since we don't have direct access to the tokenizer
        return len(text) // 4
    
    def close(self):
        """Clean up resources."""
        logger.debug("Gemini client closed")
