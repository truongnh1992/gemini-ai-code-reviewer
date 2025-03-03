from dotenv import load_dotenv
import os
from ai_providers.deepseek_provider import DeepseekProvider

def main():
    # Load environment variables from .env file
    load_dotenv()
    
    # Initialize the provider
    provider = DeepseekProvider()
    
    try:
        # Configure the provider (this will check for DEEPSEEK_API_KEY)
        provider.configure()
        
        # Test prompt for testing empty review case
        test_prompt = """Your task is reviewing pull requests. Instructions:
    - Provide the response in following JSON format:  {"reviews": [{"lineNumber":  <line_number>, "reviewComment": "<review comment>"}]}
    - Provide comments and suggestions ONLY if there is something to improve, otherwise "reviews" should be an empty array.
    - Use GitHub Markdown in comments
    - Focus on bugs, security issues, and performance problems
    - IMPORTANT: NEVER suggest adding comments to the code

Review the following code diff in the file "clean_code.py" and take the pull request title and description into account when writing the response.

Pull request title: Add utility function to handle numeric calculations
Pull request description:

---
Adding a well-tested utility function for safe numeric operations with proper type hints and error handling
---

Git diff to review:

```diff
+ from typing import Union, Optional
+ from decimal import Decimal
+
+ def calculate_total(values: list[Union[int, float, Decimal]]) -> Optional[Union[int, float, Decimal]]:
+     Calculate the total sum of numeric values.
+     if not values:
+         return None
+     try:
+         return sum(values)
+     except (TypeError, ValueError):
+         return None
```
"""
        
        # Generate review
        results = provider.generate_review(test_prompt)
        print("Raw results:", results)
        
        # Print results
        if results:
            print("Review Results:")
            for review in results:
                print(f"\nLine {review.get('lineNumber', 'N/A')}:")
                print(f"Comment: {review.get('reviewComment', 'No comment provided')}")
        else:
            print("No review comments were generated.")
            
    except ValueError as e:
        print(f"Configuration Error: {e}")
    except Exception as e:
        print(f"Unexpected Error: {e}")

if __name__ == "__main__":
    main()
