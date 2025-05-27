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

            # Create minimal Hunk object for prompt creation
            hunk = Hunk()
            hunk.content = '\n'.join(hunk_lines)

            prompt = create_prompt(file_info, hunk, pr_details)
            print("Sending prompt to Gemini...")
            ai_response = get_ai_response(prompt)
            print(f"AI response received: {ai_response}")

            if ai_response:
                # Pass hunk_data instead of hunk object
                new_comments = create_comment(file_info, hunk_data, ai_response)
                print(f"Comments created from AI response: {new_comments}")
                if new_comments:
                    comments.extend(new_comments)
                    print(f"Updated comments list: {comments}")

    print(f"\nFinal comments list: {comments}")
    return comments


def create_prompt(file: PatchedFile, hunk: Hunk, pr_details: PRDetails) -> str:
    """Creates the prompt for the Gemini model."""
    
    # Create numbered diff display
    diff_lines = hunk.content.split('\n')
    numbered_diff = []
    for i, line in enumerate(diff_lines, 1):
        numbered_diff.append(f"{i:3d} │ {line}")
    numbered_content = '\n'.join(numbered_diff)

    return f"""Your task is to review a frontend pull request for **only critical issues**.

{os.environ.get("REPO_NOTES", "")}

✅ ONLY flag if there's a **real, production-impacting problem**, such as:
1. Major Security vulnerabilities
2. Severe performance issues
3. Critical architectural flaws or logic bugs
4. Broken or missing functionality affecting core features

📦 Output format:
{{
  "reviews": [
    {{
      "lineNumber": <line>,  // For single-line issues
      "reviewComment": "<your comment>"
    }},
    {{
      "startLine": <start>,  // For multi-line blocks (optional)
      "endLine": <end>,
      "lineNumber": <main_line>,  // Anchor line
      "reviewComment": "<your comment>"
    }}
  ]
}}

PR Title: {pr_details.title}

PR Description:
---
{pr_details.description or 'No description provided'}
---

📄 Diff to review for file `{file.path}`:
```diff
{numbered_content}
"""

def get_ai_response(prompt: str) -> List[Dict[str, str]]:
    """Sends the prompt to Gemini API and retrieves the response."""
    # Use 'gemini-2.0-flash-001' as a fallback default value if the environment variable isn't set
    gemini_model = Client.GenerativeModel(os.environ.get('GEMINI_MODEL', 'gemini-2.0-flash-001'))

    generation_config = {
        "max_output_tokens": 8192,
        "temperature": 0.8,
        "top_p": 0.95,
    }

    print("===== The promt sent to Gemini is: =====")
    print(prompt)
    try:
        response = gemini_model.generate_content(prompt, generation_config=generation_config)

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

def create_comment(file: FileInfo, hunk_data: Dict[str, Any], ai_responses: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Creates comment objects from AI responses."""
    comments = []

    for ai_response in ai_responses:
        try:
            # Parse the hunk header to get the starting line number
            header = hunk_data['header']
            start_match = header.split("@@")[1].strip().split(" ")[1]
            file_start_line = int(start_match.split(",")[0].replace("+", ""))
            
            # Handle multi-line comments
            if all(k in ai_response for k in ["startLine", "endLine", "lineNumber"]):
                start_line = file_start_line + int(ai_response["startLine"]) - 1
                end_line = file_start_line + int(ai_response["endLine"]) - 1
                comment = {
                    "body": ai_response["reviewComment"],
                    "path": file.path,
                    "line": end_line,  # GitHub uses 'line' for the end line
                    "start_line": start_line,  # 'start_line' for the beginning
                    "start_side": "RIGHT",
                    "side": "RIGHT"
                }
            else:
                # Single line comment
                line_number = file_start_line + int(ai_response["lineNumber"]) - 1
                comment = {
                    "body": ai_response["reviewComment"],
                    "path": file.path,
                    "line": line_number,
                    "side": "RIGHT"
                }
            
            comments.append(comment)

        except (KeyError, TypeError, ValueError) as e:
            print(f"Error creating comment: {e}, Response: {ai_response}")
            print(f"Hunk header: {hunk_data.get('header')}")
            print(f"Line number from AI: {ai_response.get('lineNumber')}")
    
    return comments

def create_review_comment(
    owner: str,
    repo: str,
    pull_number: int,
    comments: List[Dict[str, Any]],
    summary: str = None
):
    """Creates review comments using GitHub REST API."""
    print(f"Creating review with {len(comments)} comments")

    # First get the latest commit SHA
    repo_obj = gh.get_repo(f"{owner}/{repo}")
    pr = repo_obj.get_pull(pull_number)
    commit_id = pr.get_commits().reversed[0].sha

    # First create the review with the summary
    if summary:
        pr.create_review(body=summary, event="COMMENT")

    # Create individual review comments
    api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pull_number}/comments"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    for comment in comments:
        review_data = {
            "body": comment["body"],
            "commit_id": commit_id,
            "path": comment["path"],
            "line": comment["line"],
            "side": "RIGHT"
        }

        # Add start_line if it exists for multi-line comments
        if "start_line" in comment and comment["start_line"] != comment["line"]:
            review_data["start_line"] = comment["start_line"]
            review_data["start_side"] = "RIGHT"

        response = requests.post(
            api_url,
            headers=headers,
            json=review_data
        )

        if response.status_code not in [201, 200]:
            print(f"Error creating comment: {response.text}")
            print(f"Comment data: {review_data}")
        else:
            print(f"Successfully created comment on line {comment['line']}")

    print("Review creation completed")

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

def build_file_tree(files: List[Dict[str, Any]]) -> str:
    """Build a visual tree structure of changed files."""
    def count_changes(hunks):
        changes = 0
        for hunk in hunks:
            for line in hunk.get('lines', []):
                if line.startswith('+') or line.startswith('-'):
                    changes += 1
        return changes

    tree_lines = []
    processed_dirs = set()

    for file_data in files:
        file_path = file_data.get('path', '').strip()
        if not file_path:
            continue

        hunks = file_data.get('hunks', [])
        path_parts = file_path.split('/')
        
        current_path = ""
        for i, part in enumerate(path_parts):
            current_path = current_path + part if i == 0 else current_path + '/' + part
            
            if i == len(path_parts) - 1:  # File
                prefix = "    " * i
                change_count = count_changes(hunks)
                change_text = f" ({change_count} changes)" if change_count > 0 else ""
                tree_lines.append(f"{prefix}└── {part}{change_text}")
            else:  # Directory
                if current_path not in processed_dirs:
                    prefix = "    " * i
                    tree_lines.append(f"{prefix}├── {part}/")
                    processed_dirs.add(current_path)

    return "\n".join(tree_lines)

def generate_pr_summary(parsed_diff: List[Dict[str, Any]], pr_details: PRDetails) -> str:
    """Generate a summary of the PR changes."""
    tree_str = build_file_tree(parsed_diff)
    
    prompt = f"""Analyze this pull request and provide a concise summary.
IMPORTANT: Respond ONLY in JSON format.

Pull Request Details:
Title: {pr_details.title}
Description: {pr_details.description or 'No description provided'}

File Structure:
```
{tree_str}
```

Your response must be in this exact JSON format:
{{
    "summary": {{
        "overview": "Summary of the changes made in this pull request",
        "impact": "Potential impact of these changes"
    }}
}}
"""

    try:
        gemini_model = Client.GenerativeModel(os.environ.get('GEMINI_MODEL', 'gemini-2.0-flash-001'))
        response = gemini_model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Clean up the response text
        if response_text.startswith('```json'):
            response_text = response_text[7:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        print(f"Cleaned response text: {response_text}")
        
        data = json.loads(response_text)
        
        if not isinstance(data, dict) or 'summary' not in data:
            raise ValueError("Invalid response format from Gemini")
        
        return f"""## Pull Request Summary

### Overview
{data['summary']['overview']}

### Impact
{data['summary']['impact']}

### File Structure
```
{tree_str}
```
"""
    except Exception as e:
        print(f"Error generating PR summary: {e}")
        print(f"Raw response: {response.text if 'response' in locals() else 'No response'}")
        return "Unable to generate summary"


def main():
    """Main function to execute the code review process."""
    try:
        # Get PR details
        pr_details = get_pr_details()
        
        # Get event name and validate
        event_name = os.environ.get("GITHUB_EVENT_NAME")
        if event_name == "issue_comment":
            event_data = json.load(open(os.environ["GITHUB_EVENT_PATH"], "r"))
            
            # Validate PR comment
            if not event_data.get("issue", {}).get("pull_request"):
                print("Comment was not on a pull request")
                return

            # Get diff
            diff = get_diff(pr_details.owner, pr_details.repo, pr_details.pull_number)
            if not diff:
                print("There is no diff found")
                return

            # Parse and filter diff
            parsed_diff = parse_diff(diff)
            
            # Handle exclude patterns
            exclude_patterns_raw = os.environ.get("INPUT_EXCLUDE", "")
            exclude_patterns = []
            if exclude_patterns_raw and exclude_patterns_raw.strip():
                exclude_patterns = [p.strip() for p in exclude_patterns_raw.split(",") if p.strip()]
            print(f"Exclude patterns: {exclude_patterns}")

            # Filter files
            filtered_diff = [
                file for file in parsed_diff 
                if not any(fnmatch.fnmatch(file.get('path', ''), pattern) 
                          for pattern in exclude_patterns)
            ]
            
            # Generate PR summary
            print("Generating PR summary...")
            summary = generate_pr_summary(filtered_diff, pr_details)
            
            print("Analyzing code for comments...")
            comments = analyze_code(filtered_diff, pr_details)
            
            if comments or summary:
                try:
                    create_review_comment(
                        pr_details.owner,
                        pr_details.repo,
                        pr_details.pull_number,
                        comments,
                        summary
                    )
                except Exception as e:
                    print("Error in create_review_comment:", e)
        else:
            print("Unsupported event:", os.environ.get("GITHUB_EVENT_NAME"))
            
    except Exception as error:
        print("Error in main:", error)
        raise

if __name__ == "__main__":
    main()


