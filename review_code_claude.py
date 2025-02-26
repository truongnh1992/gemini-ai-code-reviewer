import json
import os
from typing import List, Dict, Any
import anthropic
from github import Github
import difflib
import requests
import fnmatch
from unidiff import Hunk, PatchedFile, PatchSet
from embeddings_store import GuidelinesStore
# from dotenv import load_dotenv // for local env only

# Load environment variables from .env file
# load_dotenv() // for local env only

DEBUG = os.environ.get('DEBUG', 'false').lower() == 'true'

def debug_log(message):
    if DEBUG:
        print(f"DEBUG: {message}")

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

# Initialize GitHub and Anthropic clients
gh = Github(GITHUB_TOKEN)
claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Initialize guidelines store
guidelines_store = GuidelinesStore()
guidelines_store.initialize_from_markdown('coding_guidelines.md')

class PRDetails:
    def __init__(self, owner: str, repo: str, pull_number: int, title: str, description: str):
        self.owner = owner
        self.repo = repo
        self.pull_number = pull_number
        self.title = title
        self.description = description


def get_pr_details() -> PRDetails:
    """Retrieves details of the pull request from GitHub Actions event payload."""
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    debug_log(f"Event path: {event_path}")
    
    with open(event_path, "r") as f:
        event_data = json.load(f)
    
    debug_log(f"Event data: {json.dumps(event_data, indent=2)}")

    # Handle PR labeled event
    if "pull_request" in event_data:
        pull_number = event_data["pull_request"]["number"]
        repo_full_name = event_data["repository"]["full_name"]
    else:
        raise ValueError("Unsupported event type")

    debug_log(f"PR number: {pull_number}")
    debug_log(f"Repo: {repo_full_name}")

    owner, repo = repo_full_name.split("/")
    repo_obj = gh.get_repo(repo_full_name)
    pr = repo_obj.get_pull(pull_number)

    return PRDetails(owner, repo, pull_number, pr.title, pr.body)


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
    """Analyzes the code changes using Claude and generates review comments."""
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
            print("Sending prompt to Claude...")
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
    """Creates the prompt for the Claude model."""
    # Get relevant guidelines based on the code being reviewed
    relevant_guidelines = guidelines_store.get_relevant_guidelines(
        code_snippet=hunk.content,
        file_path=file.path
    )
    
    guidelines_text = "\n".join(relevant_guidelines)
    
    return f"""Your task is reviewing pull requests according to our coding guidelines. Instructions:
    - Provide the response in following JSON format: {{"reviews": [{{"lineNumber": <line_number>, "reviewComment": "<review comment>"}}]}}
    - Provide comments and suggestions ONLY if there is something to improve, otherwise "reviews" should be an empty array
    - Use GitHub Markdown in comments
    - Focus on bugs, security issues, performance problems, and adherence to our coding guidelines
    - IMPORTANT: NEVER suggest adding comments to the code

Here are the relevant coding guidelines for this code:

{guidelines_text}

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
    """Sends the prompt to Claude API and retrieves the response."""
    model = os.environ.get('CLAUDE_MODEL', 'claude-3-5-sonnet-20240620')

    print("===== The prompt sent to Claude is: =====")
    print(prompt)
    try:
        response = claude_client.messages.create(
            model=model,
            max_tokens=4000,
            temperature=0.7,
            system="You are an expert code reviewer. Provide feedback in the requested JSON format.",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        response_text = response.content[0].text
        
        # Extract JSON if it's wrapped in code blocks
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
        print(f"Error during Claude API call: {e}")
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
            body="Claude Code Reviewer Comments",
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
    try:
        debug_log("Starting code review process")
        pr_details = get_pr_details()
        debug_log(f"Got PR details: {pr_details.__dict__}")

        diff = get_diff(pr_details.owner, pr_details.repo, pr_details.pull_number)
        debug_log(f"Got diff of length: {len(diff)}")
        
        if not diff:
            debug_log("No diff found")
            return

        parsed_diff = parse_diff(diff)
        debug_log(f"Parsed diff into {len(parsed_diff)} files")

        # Get and clean exclude patterns
        exclude_patterns_raw = os.environ.get("INPUT_EXCLUDE", "")
        debug_log(f"Raw exclude patterns: {exclude_patterns_raw}")
        
        exclude_patterns = []
        if exclude_patterns_raw and exclude_patterns_raw.strip():
            exclude_patterns = [p.strip() for p in exclude_patterns_raw.split(",") if p.strip()]
        debug_log(f"Processed exclude patterns: {exclude_patterns}")

        # Filter files
        filtered_diff = []
        for file in parsed_diff:
            file_path = file.get('path', '')
            should_exclude = any(fnmatch.fnmatch(file_path, pattern) for pattern in exclude_patterns)
            if should_exclude:
                debug_log(f"Excluding file: {file_path}")
                continue
            filtered_diff.append(file)
            debug_log(f"Including file: {file_path}")

        debug_log(f"Files to analyze after filtering: {[f.get('path', '') for f in filtered_diff]}")
        
        comments = analyze_code(filtered_diff, pr_details)
        debug_log(f"Generated {len(comments)} comments")
        
        if comments:
            try:
                create_review_comment(
                    pr_details.owner, pr_details.repo, pr_details.pull_number, comments
                )
                debug_log("Successfully created review comments")
            except Exception as e:
                debug_log(f"Error in create_review_comment: {str(e)}")
                raise
    except Exception as error:
        debug_log(f"Error in main: {str(error)}")
        raise

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        debug_log(f"Fatal error: {str(error)}")
        raise 