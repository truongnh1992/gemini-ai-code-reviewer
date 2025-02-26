import os
import json
import openai
from unidiff import Hunk

# This is a simple test script to verify that our OpenAI integration works correctly
# You need to set the OPENAI_API_KEY environment variable before running this script

# Check if OPENAI_API_KEY is set
if not os.environ.get('OPENAI_API_KEY'):
    print("Error: OPENAI_API_KEY environment variable is not set.")
    print("Please set it with: export OPENAI_API_KEY='your-api-key'")
    exit(1)

# Initialize OpenAI client
openai.api_key = os.environ.get('OPENAI_API_KEY')

# Sample code diff to review
sample_diff = """@@ -1,5 +1,5 @@
 def calculate_total(items):
-    total = 0
+    total = 1  # Initialize with 1 instead of 0
     for item in items:
         total += item.price
     return total"""

# Create a mock hunk
hunk = Hunk()
hunk.source_start = 1
hunk.source_length = 5
hunk.target_start = 1
hunk.target_length = 5
hunk.content = sample_diff

# Create a mock file
class MockFile:
    def __init__(self, path):
        self.path = path

file = MockFile("shopping_cart.py")

# Create a mock PR details
class MockPRDetails:
    def __init__(self):
        self.title = "Fix calculation bug"
        self.description = "This PR fixes a calculation bug in the shopping cart."

pr_details = MockPRDetails()

# Create the prompt
prompt = f"""Your task is reviewing pull requests. Instructions:
    - Provide the response in following JSON format:  {{"reviews": [{{"lineNumber":  <line_number>, "reviewComment": "<review comment>"}}]}}
    - Provide comments and suggestions ONLY if there is something to improve, otherwise "reviews" should be an empty array.
    - Use GitHub Markdown in comments
    - Focus on bugs, security issues, and performance problems
    - IMPORTANT: NEVER suggest adding comments to the code

Review the following code diff in the file "{file.path}" and take the pull request title and description into account when writing the response.

Pull request title: {pr_details.title}
Pull request description:

---
{pr_details.description}
---

Git diff to review:

```diff
{hunk.content}
```
"""

print("Sending prompt to OpenAI...")
try:
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are an expert code reviewer. Provide feedback in the requested JSON format."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=4000
    )

    response_text = response.choices[0].message.content.strip()
    print("\nRaw response from OpenAI:")
    print(response_text)

    # Clean up the response if it's wrapped in markdown code blocks
    if response_text.startswith('```json'):
        response_text = response_text[7:]  # Remove ```json
    if response_text.endswith('```'):
        response_text = response_text[:-3]  # Remove ```
    response_text = response_text.strip()

    print("\nCleaned response:")
    print(response_text)

    # Parse the JSON response
    try:
        data = json.loads(response_text)
        print("\nParsed JSON data:")
        print(json.dumps(data, indent=2))

        if "reviews" in data and isinstance(data["reviews"], list):
            reviews = data["reviews"]
            print("\nReview comments:")
            for review in reviews:
                if "lineNumber" in review and "reviewComment" in review:
                    print(f"Line {review['lineNumber']}: {review['reviewComment']}")
                else:
                    print(f"Invalid review format: {review}")
        else:
            print("Error: Response doesn't contain valid 'reviews' array")
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response: {e}")
except Exception as e:
    print(f"Error during OpenAI API call: {e}")

print("\nTest completed.")