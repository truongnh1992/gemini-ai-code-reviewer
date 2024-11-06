import json
import os
from typing import List, Dict, Any
import google.generativeai as Client
from github import Github
import difflib
import requests
import fnmatch
from unidiff import Hunk, PatchedFile, PatchSet

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]

# Initialize GitHub and Gemini clients
gh = Github(GITHUB_TOKEN)
gemini_client = Client.configure(api_key=os.environ.get('GEMINI_API_KEY'))


class PRDetails:
    def __init__(self, owner: str, repo: str, pull_number: int, title: str, description: str):
        self.owner = owner
        self.repo = repo
        self.pull_number = pull_number
        self.title = title
        self.description = description


def get_pr_details() -> PRDetails:
    """Retrieves details of the pull request from GitHub Actions event payload."""
    with open(os.environ["GITHUB_EVENT_PATH"], "r") as f:
        event_data = json.load(f)

    # Handle comment trigger differently from direct PR events
    if "issue" in event_data and "pull_request" in event_data["issue"]:
        # For comment triggers, we need to get the PR number from the issue
        pull_number = event_data["issue"]["number"]
        repo_full_name = event_data["repository"]["full_name"]
    else:
        # Original logic for direct PR events
        pull_number = event_data["number"]
        repo_full_name = event_data["repository"]["full_name"]

    owner, repo = repo_full_name.split("/")

    repo = gh.get_repo(repo_full_name)
    pr = repo.get_pull(pull_number)

    return PRDetails(owner, repo.name, pull_number, pr.title, pr.body)


def get_diff(owner: str, repo: str, pull_number: int) -> str:
    """Fetches the diff of the pull request from GitHub API."""
    # Use the correct repository name format
    repo_name = f"{owner}/{repo}"
    print(f"Attempting to get diff for: {repo_name} PR#{pull_number}")

    repo = gh.get_repo(repo_name)
    pr = repo.get_pull(pull_number)
    
    # Use the GitHub API URL directly
    api_url = f"https://api.github.com/repos/{repo_name}/pulls/{pull_number}"

    headers = {
        'Authorization': f'Bearer {GITHUB_TOKEN}',  # Changed to Bearer format
        'Accept': 'application/vnd.github.v3.diff'
    }

    response = requests.get(f"{api_url}.diff", headers=headers)
    
    if response.status_code == 200:
        diff = response.text
        print(f"Retrieved diff length: {len(diff) if diff else 0}")
        return diff
    else:
        print(f"Failed to get diff. Status code: {response.status_code}")
        print(f"Response content: {response.text}")
        print(f"URL attempted: {api_url}.diff")
        return ""


def analyze_code(parsed_diff: List[Dict[str, Any]], pr_details: PRDetails) -> List[Dict[str, Any]]:
    """Analyzes the code changes using Gemini and generates review comments."""
    print("Starting analyze_code...")
    print(f"Number of files to analyze: {len(parsed_diff)}")
    comments = []
    #print(f"Initial comments list: {comments}")
    
    for file_data in parsed_diff:
        file_path = file_data.get('path', '')
        print(f"\nProcessing file: {file_path}")

        if not file_path or file_path == "/dev/null":
            continue

        class FileInfo:
            def __init__(self, path):
                self.path = path

        file_info = FileInfo(file_path)

        hunks = file_data.get('hunks', [])
        print(f"Hunks in file: {len(hunks)}")
        
        for hunk_data in hunks:
            print(f"\nHunk content: {json.dumps(hunk_data, indent=2)}")
            hunk_lines = hunk_data.get('lines', [])
            print(f"Number of lines in hunk: {len(hunk_lines)}")

            if not hunk_lines:
                continue
                
            hunk = Hunk()
            hunk.source_start = 1
            hunk.source_length = len(hunk_lines)
            hunk.target_start = 1
            hunk.target_length = len(hunk_lines)
            hunk.content = '\n'.join(hunk_lines)
            
            prompt = create_prompt(file_info, hunk, pr_details)
            print("Sending prompt to Gemini...")
            ai_response = get_ai_response(prompt)
            print(f"AI response received: {ai_response}")
            
            if ai_response:
                new_comments = create_comment(file_info, hunk, ai_response)
                print(f"Comments created from AI response: {new_comments}")
                if new_comments:
                    comments.extend(new_comments)
                    print(f"Updated comments list: {comments}")

    print(f"\nFinal comments list: {comments}")
    return comments


def create_prompt(file: PatchedFile, hunk: Hunk, pr_details: PRDetails) -> str:
    """Creates the prompt for the Gemini model."""
    return f"""Your task is reviewing pull requests. Instructions:
    - Provide the response in following JSON format:  {{"reviews": [{{"lineNumber":  <line_number>, "reviewComment": "<review comment>"}}]}}
    - Provide comments and suggestions ONLY if there is something to improve, otherwise "reviews" should be an empty array.
    - Use GitHub Markdown in comments
    - Focus on bugs, security issues, and performance problems
    - IMPORTANT: NEVER suggest adding comments to the code

Review the following code diff in the file "{file.path}" and take the pull request title and description into account when writing the response.
  
Pull request title: {pr_details.title}
Pull request description:

---
{pr_details.description or 'No description provided'}
---

Git diff to review:

```diff
{hunk.content}
```
"""

def get_ai_response(prompt: str) -> List[Dict[str, str]]:
    """Sends the prompt to Gemini API and retrieves the response."""
    # Use 'gemini-1.5-flash-002' as a fallback default value if the environment variable isn't set
    gemini_model = Client.GenerativeModel(os.environ.get('GEMINI_MODEL', 'gemini-1.5-flash-002'))
    print("===== The promt sent to Gemini is: =====")
    print(prompt)
    try:
        response = gemini_model.generate_content(prompt)

        response_text = response.text.strip()
        if response_text.startswith('```json'):
            response_text = response_text[7:]  # Remove ```json
        if response_text.endswith('```'):
            response_text = response_text[:-3]  # Remove ```
        response_text = response_text.strip()
        
        print(f"Cleaned response text: {response_text}")
        
        try:
            data = json.loads(response_text)
            print(f"Parsed JSON data: {data}")
            
            if "reviews" in data and isinstance(data["reviews"], list):
                reviews = data["reviews"]
                valid_reviews = []
                for review in reviews:
                    if "lineNumber" in review and "reviewComment" in review:
                        valid_reviews.append(review)
                    else:
                        print(f"Invalid review format: {review}")
                return valid_reviews
            else:
                print("Error: Response doesn't contain valid 'reviews' array")
                print(f"Response content: {data}")
                return []
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON response: {e}")
            print(f"Raw response: {response_text}")
            return []
    except Exception as e:
        print(f"Error during Gemini API call: {e}")
        return []

class FileInfo:
    """Simple class to hold file information."""
    def __init__(self, path: str):
        self.path = path

def create_comment(file: FileInfo, hunk: Hunk, ai_responses: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Creates comment objects from AI responses."""
    print("AI responses in create_comment:", ai_responses)
    print(f"Hunk details - start: {hunk.source_start}, length: {hunk.source_length}")
    print(f"Hunk content:\n{hunk.content}")
    
    comments = []
    for ai_response in ai_responses:
        try:
            line_number = int(ai_response["lineNumber"])
            print(f"Original AI suggested line: {line_number}")
            
            # Ensure the line number is within the hunk's range
            if line_number < 1 or line_number > hunk.source_length:
                print(f"Warning: Line number {line_number} is outside hunk range")
                continue
                
            comment = {
                "body": ai_response["reviewComment"],
                "path": file.path,
                "position": line_number
            }
            print(f"Created comment: {json.dumps(comment, indent=2)}")
            comments.append(comment)
            
        except (KeyError, TypeError, ValueError) as e:
            print(f"Error creating comment from AI response: {e}, Response: {ai_response}")
    return comments

def create_review_comment(
    owner: str,
    repo: str,
    pull_number: int,
    comments: List[Dict[str, Any]],
):
    """Submits the review comments to the GitHub API."""
    print(f"Attempting to create {len(comments)} review comments")
    print(f"Comments content: {json.dumps(comments, indent=2)}")

    repo = gh.get_repo(f"{owner}/{repo}")
    pr = repo.get_pull(pull_number)
    try:
        # Create the review with only the required fields
        review = pr.create_review(
            body="Gemini AI Code Reviewer Comments",
            comments=comments,
            event="COMMENT"
        )
        print(f"Review created successfully with ID: {review.id}")
        
    except Exception as e:
        print(f"Error creating review: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Review payload: {comments}")

def parse_diff(diff_str: str) -> List[Dict[str, Any]]:
    """Parses the diff string and returns a structured format."""
    files = []
    current_file = None
    current_hunk = None
    
    for line in diff_str.splitlines():
        if line.startswith('diff --git'):
            if current_file:
                files.append(current_file)
            current_file = {'path': '', 'hunks': []}
            
        elif line.startswith('--- a/'):
            if current_file:
                current_file['path'] = line[6:]
                
        elif line.startswith('+++ b/'):
            if current_file:
                current_file['path'] = line[6:]
                
        elif line.startswith('@@'):
            if current_file:
                current_hunk = {'header': line, 'lines': []}
                current_file['hunks'].append(current_hunk)
                
        elif current_hunk is not None:
            current_hunk['lines'].append(line)
            
    if current_file:
        files.append(current_file)
        
    return files



def main():
    """Main function to execute the code review process."""
    pr_details = get_pr_details()
    event_data = json.load(open(os.environ["GITHUB_EVENT_PATH"], "r"))

    event_name = os.environ.get("GITHUB_EVENT_NAME")
    if event_name == "issue_comment":
        # Process comment trigger
        if not event_data.get("issue", {}).get("pull_request"):
            print("Comment was not on a pull request")
            return

        diff = get_diff(pr_details.owner, pr_details.repo, pr_details.pull_number)
        if not diff:
            print("There is no diff found")
            return

        parsed_diff = parse_diff(diff)

        exclude_patterns = os.environ.get("INPUT_EXCLUDE", "").split(",")
        exclude_patterns = [s.strip() for s in exclude_patterns]

        filtered_diff = [
            file
            for file in parsed_diff
            if not any(fnmatch.fnmatch(file.get('path', ''), pattern) for pattern in exclude_patterns)
        ]

        comments = analyze_code(filtered_diff, pr_details)
        if comments:
            try:
                create_review_comment(
                    pr_details.owner, pr_details.repo, pr_details.pull_number, comments
                )
            except Exception as e:
                print("Error in create_review_comment:", e)
    else:
        print("Unsupported event:", os.environ.get("GITHUB_EVENT_NAME"))
        return


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Error:", error)
