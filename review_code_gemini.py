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
    summary: str,
):
    """Submits the review comments to the GitHub API."""
    print(f"Attempting to create {len(comments)} review comments")
    print(f"Comments content: {json.dumps(comments, indent=2)}")

    repo = gh.get_repo(f"{owner}/{repo}")
    pr = repo.get_pull(pull_number)
    try:
        # Create the review with summary and comments
        review_body = f"""# AI Code Review Summary

{summary}

---
### Detailed Comments Below
"""
        review = pr.create_review(
            body=review_body,
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

def generate_pr_summary(parsed_diff: List[Dict[str, Any]], pr_details: PRDetails) -> str:
    """Generates an overall summary of the pull request using Gemini."""
    
    # Create a visual tree structure of changes
    def build_tree(files):
        """Build a visual tree structure of changed files."""
        def count_actual_changes(hunks):
            """Count actual additions and deletions in hunks."""
            changes = 0
            for hunk in hunks:
                for line in hunk.get('lines', []):
                    if (line.startswith('+') or line.startswith('-')) and not line[1:].isspace():
                        changes += 1
            return changes

        def sort_path(path):
            """Sort paths so directories come before files."""
            parts = path.split('/')
            # Directories sort before files in the same level
            return [(p, 0) if i < len(parts)-1 else (p, 1) for i, p in enumerate(parts)]

        # Sort files to maintain consistent order
        sorted_files = sorted(files, key=lambda x: sort_path(x.get('path', '')))
        
        tree_lines = []
        processed_dirs = set()

        for idx, file_data in enumerate(sorted_files):
            file_path = file_data.get('path', '').strip()
            if not file_path:  # Skip empty paths
                continue

            hunks = file_data.get('hunks', [])
            path_parts = file_path.split('/')
            
            current_path = ""
            for i, part in enumerate(path_parts):
                current_path = current_path + part if i == 0 else current_path + '/' + part
                is_last_component = i == len(path_parts) - 1
                
                if is_last_component:  # File
                    prefix = "    " * i
                    is_last_file = idx == len(sorted_files) - 1
                    branch = "└── " if is_last_file else "├── "
                    
                    # Count actual changes
                    change_count = count_actual_changes(hunks)
                    # Only show changes if there are any
                    change_text = f" ({change_count} changes)" if change_count > 0 else ""
                    tree_lines.append(f"{prefix}{branch}{part}{change_text}")
                else:  # Directory
                    if current_path not in processed_dirs:
                        prefix = "    " * i
                        # Check if this is the last directory at this level
                        is_last_dir = not any(f.get('path', '').startswith(current_path + '/')
                                            for f in sorted_files[idx+1:])
                        branch = "└── " if is_last_dir else "├── "
                        tree_lines.append(f"{prefix}{branch}{part}/")
                        processed_dirs.add(current_path)
        
        return tree_lines

    # Generate the tree structure
    tree = build_tree(parsed_diff)
    tree_str = "\n".join(tree)

    # Build the code diffs section with file names as headers
    code_diffs = []
    for file_data in parsed_diff:
        file_path = file_data.get('path', '')
        hunks = file_data.get('hunks', [])
        
        # Add a header for each file with markdown formatting
        code_diffs.append(f"\n## File: `{file_path}`")
        
        for idx, hunk in enumerate(hunks):
            # Add hunk number for better reference
            code_diffs.append(f"\n### Change {idx + 1}:")
            code_diffs.append("```diff\n" + "\n".join(hunk.get('lines', [])) + "\n```")

    prompt = f"""Analyze this pull request and generate a comprehensive review.

Pull Request Details:
Title: {pr_details.title}
Description: {pr_details.description or 'No description provided'}

File Structure:
```
{tree_str}
```

Code Changes:
{chr(10).join(code_diffs)}

Please provide your analysis in the following format:
1. Summary of Changes (2-3 sentences)
2. Potential Impact of These Changes
3. File Structure (as shown above)

Keep the response concise and technical."""

    try:
        gemini_model = Client.GenerativeModel(os.environ.get('GEMINI_MODEL', 'gemini-2.0-flash-001'))
        response = gemini_model.generate_content(prompt)
        
        # Format the final response with the tree structure
        formatted_response = f"""## Pull Request Review

{response.text.strip()}

## File Structure
```
{tree_str}
```"""
        return formatted_response
    except Exception as e:
        print(f"Error generating PR summary: {e}")
        return "Unable to generate PR summary"

def analyze_pr(parsed_diff: List[Dict[str, Any]], pr_details: PRDetails) -> tuple[str, List[Dict[str, Any]]]:
    """Analyzes the entire PR and generates both summary and comments in one go."""
    
    def build_tree(files):
        """Build a visual tree structure of changed files."""
        def count_actual_changes(hunks):
            """Count actual additions and deletions in hunks."""
            changes = 0
            for hunk in hunks:
                for line in hunk.get('lines', []):
                    # Only count lines that start with + or - and ignore whitespace-only changes
                    if (line.startswith('+') or line.startswith('-')) and not line[1:].isspace():
                        changes += 1
            return changes

        def sort_path(path):
            """Sort paths so directories come before files."""
            parts = path.split('/')
            # Directories sort before files in the same level
            return [(p, 0) if i < len(parts)-1 else (p, 1) for i, p in enumerate(parts)]

        # Sort files to maintain consistent order
        sorted_files = sorted(files, key=lambda x: sort_path(x.get('path', '')))
        
        tree_lines = []
        processed_dirs = set()

        for idx, file_data in enumerate(sorted_files):
            file_path = file_data.get('path', '').strip()
            if not file_path:  # Skip empty paths
                continue

            hunks = file_data.get('hunks', [])
            path_parts = file_path.split('/')
            
            current_path = ""
            for i, part in enumerate(path_parts):
                current_path = current_path + part if i == 0 else current_path + '/' + part
                is_last_component = i == len(path_parts) - 1
                
                if is_last_component:  # File
                    prefix = "    " * i
                    is_last_file = idx == len(sorted_files) - 1
                    branch = "└── " if is_last_file else "├── "
                    
                    # Count actual changes
                    change_count = count_actual_changes(hunks)
                    # Only show changes if there are any
                    change_text = f" ({change_count} changes)" if change_count > 0 else ""
                    tree_lines.append(f"{prefix}{branch}{part}{change_text}")
                else:  # Directory
                    if current_path not in processed_dirs:
                        prefix = "    " * i
                        # Check if this is the last directory at this level
                        is_last_dir = not any(f.get('path', '').startswith(current_path + '/')
                                            for f in sorted_files[idx+1:])
                        branch = "└── " if is_last_dir else "├── "
                        tree_lines.append(f"{prefix}{branch}{part}/")
                        processed_dirs.add(current_path)
        
        return tree_lines

    # Generate tree structure
    tree = build_tree(parsed_diff)
    tree_str = "\n".join(tree)

    # Build complete diff with file structure
    code_sections = []
    for file_data in parsed_diff:
        file_path = file_data.get('path', '')
        hunks = file_data.get('hunks', [])
        
        # Add file header with markdown
        code_sections.append(f"\n## `{file_path}`")
        
        for idx, hunk in enumerate(hunks):
            code_sections.append(f"\n### Change {idx + 1}:")
            code_sections.append("```diff\n" + "\n".join(hunk.get('lines', [])) + "\n```")

    prompt = f"""Analyze this pull request and provide both a summary and specific code reviews.

Pull Request Details:
Title: {pr_details.title}
Description: {pr_details.description or 'No description provided'}

File Structure:
```
{tree_str}
```

Code Changes:
{chr(10).join(code_sections)}

Provide your response in the following JSON format:
{{
    "summary": {{
        "overview": "2-3 sentences describing the changes",
        "impact": "Potential impact of these changes",
        "fileStructure": "Description of the file structure changes"
    }},
    "reviews": [
        {{
            "file": "filename",
            "lineNumber": line_number,
            "reviewComment": "specific review comment"
        }}
    ]
}}

Focus on:
- Technical accuracy
- Security issues
- Performance problems
- Best practices
- NEVER suggest adding comments to code
"""

    try:
        gemini_model = Client.GenerativeModel(os.environ.get('GEMINI_MODEL', 'gemini-2.0-flash-001'))
        response = gemini_model.generate_content(prompt)
        
        # Parse the response
        response_text = response.text.strip()
        if response_text.startswith('```json'):
            response_text = response_text[7:-3]  # Remove ```json and ```

        data = json.loads(response_text)
        
        # Format summary
        summary = f"""## Summary
{data['summary']['overview']}

### Impact
{data['summary']['impact']}

### File Structure
```
{tree_str}
```
"""
        
        # Format comments
        comments = []
        for review in data.get('reviews', []):
            comments.append({
                "body": review['reviewComment'],
                "path": review['file'],
                "position": review['lineNumber']
            })
        
        return summary, comments
        
    except Exception as e:
        print(f"Error in analyze_pr: {e}")
        return "Unable to generate review", []

def main():
    """Main function to execute the code review process."""
    pr_details = get_pr_details()
    event_data = json.load(open(os.environ["GITHUB_EVENT_PATH"], "r"))

    event_name = os.environ.get("GITHUB_EVENT_NAME")
    if event_name == "issue_comment":
        if not event_data.get("issue", {}).get("pull_request"):
            print("Comment was not on a pull request")
            return

        diff = get_diff(pr_details.owner, pr_details.repo, pr_details.pull_number)
        if not diff:
            print("There is no diff found")
            return

        parsed_diff = parse_diff(diff)
        
        # Filter files
        exclude_patterns = [p.strip() for p in os.environ.get("INPUT_EXCLUDE", "").split(",") if p.strip()]
        filtered_diff = [
            file for file in parsed_diff 
            if not any(fnmatch.fnmatch(file.get('path', ''), pattern) for pattern in exclude_patterns)
        ]

        # Generate both summary and comments in one go
        print("Analyzing PR...")
        summary, comments = analyze_pr(filtered_diff, pr_details)
        
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


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Error:", error)
