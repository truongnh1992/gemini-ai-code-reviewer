import json
import os
from typing import List, Dict, Any
import google.generativeai as Client
from github import Github
import difflib
import fnmatch
from unidiff import Hunk, PatchedFile, PatchSet

# Get input values from environment variables (GitHub Actions)
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

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
    repo_full_name = event_data["repository"]["full_name"]
    owner, repo = repo_full_name.split("/")
    pull_number = event_data["number"]

    repo = gh.get_repo(repo_full_name)
    pr = repo.get_pull(pull_number)

    return PRDetails(owner, repo.name, pull_number, pr.title, pr.body)


def get_diff(owner: str, repo: str, pull_number: int) -> str:
    """Fetches the diff of the pull request from GitHub API."""
    repo = gh.get_repo(f"{owner}/{repo}")
    pr = repo.get_pull(pull_number)
    commit = pr.get_commits().reversed[0]
    diff = ""
    for file in commit.files:
        try:
            # Try accessing 'content' first
            current_content = file.raw_data["content"]
        except KeyError:
            try:
                # If 'content' is missing, use 'blob_url'
                from urllib.request import urlopen
                with urlopen(file.raw_data["blob_url"]) as f:
                    current_content = f.read().decode('utf-8')
            except Exception as e:
                print(f"Error fetching content for {file.filename}: {e}")
                continue  # Skip this file if content retrieval fails

        # Generate the diff
        diff_lines = difflib.unified_diff(
            file.raw_data.get("content", "").splitlines(keepends=True),  # Handle potential missing 'content'
            current_content.splitlines(keepends=True),
            fromfile=file.raw_data.get("filename", "old_file"),
            tofile=file.filename
        )
        diff += ''.join(diff_lines) + "\n"
    return diff


def analyze_code(parsed_diff: List[PatchedFile], pr_details: PRDetails) -> List[Dict[str, Any]]:
    """Analyzes the code changes using Gemini and generates review comments."""
    comments = []
    for file in parsed_diff:
        if file.to == "/dev/null":
            continue  # Ignore deleted files
        for hunk in file.hunks:
            prompt = create_prompt(file, hunk, pr_details)
            ai_response = get_ai_response(prompt)
            if ai_response:
                new_comments = create_comment(file, hunk, ai_response)
                if new_comments:
                    comments.extend(new_comments)
    return comments


def create_prompt(file: PatchedFile, hunk: Hunk, pr_details: PRDetails) -> str:
    """Creates the prompt for the Gemini model."""
    return f"""Your task is to review pull requests. Instructions:
    - Provide the response in following JSON format:  {{"reviews": [{{"lineNumber":  <line_number>, "reviewComment": "<review comment>"}}]}}
    - Do not give positive comments or compliments.
    - Provide comments and suggestions ONLY if there is something to improve, otherwise "reviews" should be an empty array.
    - Write the comment in GitHub Markdown format.
    - Use the given description only for the overall context and only comment the code.
    - IMPORTANT: NEVER suggest adding comments to the code.

Review the following code diff in the file "{file.to}" and take the pull request title and description into account when writing the response.
  
Pull request title: {pr_details.title}
Pull request description:

---
{pr_details.description}
---

Git diff to review:

```diff
{hunk.content}
{chr(10).join([f"{c.ln if c.ln else c.ln2} {c.content}" for c in hunk.changes])}
```
"""

def get_ai_response(prompt: str) -> List[Dict[str, str]] | None:
    """Sends the prompt to Gemini API and retrieves the response."""
    try:
        response = gemini_client.generate_text(
            prompt=prompt,
            model="models/code-bison-001",
            temperature=0.2,
            max_output_tokens=700,
        )
        reviews = json.loads(response.result.strip())["reviews"]
        return reviews
    except Exception as e:
        print(f"Error during Gemini API call: {e}")
    return None

def create_comment(file: PatchedFile, hunk: Hunk, ai_responses: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Creates comment objects from AI responses."""
    return [
        {
            "body": ai_response["reviewComment"],
            "path": file.to,
            "line": int(ai_response["lineNumber"]),
        }
for ai_response in ai_responses
if file.to
]

def create_review_comment(
    owner: str,
    repo: str,
    pull_number: int,
    comments: List[Dict[str, Any]],
):
    """Submits the review comments to the GitHub API."""
    repo = gh.get_repo(f"{owner}/{repo}")
    pr = repo.get_pull(pull_number)
    pr.create_review(comments=comments, event="COMMENT")

def parse_diff(diff_str: str) -> List[PatchedFile]:
    """Parses the diff string and returns a list of PatchedFile objects."""
    patch_set = PatchSet(diff_str)
    return list(patch_set)

def main():
    """Main function to execute the code review process."""
    pr_details = get_pr_details()
    event_data = json.load(open(os.environ["GITHUB_EVENT_PATH"], "r"))
    if event_data["action"] == "opened":
        diff = get_diff(pr_details.owner, pr_details.repo, pr_details.pull_number)
        if not diff:
            print("No diff found")
            return

        parsed_diff = parse_diff(diff)

        exclude_patterns = os.environ.get("INPUT_EXCLUDE", "").split(",")
        exclude_patterns = [s.strip() for s in exclude_patterns]

        filtered_diff = [
            file
            for file in parsed_diff
            if not any(fnmatch.fnmatch(file.to or "", pattern) for pattern in exclude_patterns)
        ]

        comments = analyze_code(filtered_diff, pr_details)
        if comments:
            create_review_comment(
                pr_details.owner, pr_details.repo, pr_details.pull_number, comments
            )
    elif event_data["action"] == "synchronize":
        diff = get_diff(pr_details.owner, pr_details.repo, pr_details.pull_number)
        if not diff:
            print("No diff found")
            return

        parsed_diff = parse_diff(diff)

        exclude_patterns = os.environ.get("INPUT_EXCLUDE", "").split(",")
        exclude_patterns = [s.strip() for s in exclude_patterns]

        filtered_diff = [
            file
            for file in parsed_diff
            if not any(fnmatch.fnmatch(file.to or "", pattern) for pattern in exclude_patterns)
        ]

        comments = analyze_code(filtered_diff, pr_details)
        if comments:
            create_review_comment(
                pr_details.owner, pr_details.repo, pr_details.pull_number, comments
            )
    else:
        print("Unsupported event:", os.environ.get("GITHUB_EVENT_NAME"))
        return


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Error:", error)
