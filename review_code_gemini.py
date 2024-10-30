import json
import os
from typing import List, Dict, Any
import google.generativeai as Client
from github import Github
import difflib
import fnmatch
from unidiff import Hunk, PatchedFile, PatchSet

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


def analyze_code(parsed_diff: List[Dict[str, Any]], pr_details: PRDetails) -> List[Dict[str, Any]]:
    """Analyzes the code changes using Gemini and generates review comments."""
    print("Parsed diff:", parsed_diff)
    comments = []
    for file_data in parsed_diff:
        file_path = file_data["path"]
        if file_path == "/dev/null":
            continue  # Ignore deleted files
        for hunk_data in file_data["hunks"]:
            hunk_content = "\n".join(hunk_data["lines"])
            prompt = create_prompt(file_path, hunk_content, pr_details)  # Adjust create_prompt accordingly
            ai_response = get_ai_response(prompt)
            if ai_response:
                # Adjust create_comment to use file_path and line numbers from hunk_data["lines"]
                new_comments = create_comment(file_path, hunk_data, ai_response)
                if new_comments:
                    print("New comments generated:", new_comments)
                    comments.extend(new_comments)
    print("Comments before returning:", comments)
    return comments


def create_prompt(file: PatchedFile, hunk: Hunk, pr_details: PRDetails) -> str:
    """Creates the prompt for the Gemini model."""
    return f"""Your task is reviewing pull requests. Instructions:
    - Do not give positive comments or compliments.
    - Provide comments and suggestions ONLY if there is something to improve, otherwise "reviews" should be an empty array.
    - Write the comment in GitHub Markdown format.
    - Use the given description only for the overall context and only comment the code.
    - IMPORTANT: NEVER suggest adding comments to the code.

Review the following code diff in the file "{file.path}" and take the pull request title and description into account when writing the response.
  
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

def get_ai_response(prompt: str) -> List[Dict[str, str]]:
    """Sends the prompt to Gemini API and retrieves the response."""
    print("===== The promt =====")
    print(prompt)
    try:
        response = gemini_client.generate_text(
            prompt=prompt,
            model="gemini-1.5-pro-002",
            temperature=0.2,
            max_output_tokens=700,
        )
        print(f"Raw Gemini response: {response.result}")  # Print raw response
        try:
            data = json.loads(response.result.strip())
            if "reviews" in data and isinstance(data["reviews"], list):
                reviews = data["reviews"]
                # Check if each review item has the required keys
                # for review in reviews:
                #     if not ("lineNumber" in review and "reviewComment" in review):
                #         print(f"Incomplete review item: {review}")
                #         return []
                return reviews
            else:
                print("Error: 'reviews' key not found or is not a list in Gemini response")
                return []
        except json.JSONDecodeError as e:
            print(f"Error decoding Gemini response: {e}")
            return []
    except Exception as e:
        print(f"Error during Gemini API call: {e}")
        return []

def create_comment(file: PatchedFile, hunk: Hunk, ai_responses: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Creates comment objects from AI responses."""
    print("AI responses in create_comment:", ai_responses)
    comments = []
    for ai_response in ai_responses:
        try:
            line_number = hunk.source_start + int(ai_response["lineNumber"]) - 1
            print(f"Creating comment for line: {line_number}")  # Debugging print
            comments.append({
                "body": ai_response["reviewComment"],
                "path": file.path,
                "line": line_number,
            })
        except (KeyError, TypeError, ValueError) as e:  # Catch ValueError for line number conversion
            print(f"Error creating comment from AI response: {e}, Response: {ai_response}")
    return comments

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

def parse_diff(diff_str: str) -> List[Dict[str, Any]]:
    """Parses the diff string using difflib and returns a list of file changes."""
    files = []
    current_file = None
    diff_lines = diff_str.splitlines()
    for line in diff_lines:
        if line.startswith("--- a/"):
            current_file = {"path": line[6:], "hunks": []}
            files.append(current_file)
        elif line.startswith("+++ b/"):
            if current_file is not None:  # Check if current_file is initialized
                current_file["path"] = line[6:]
        elif line.startswith("@@"):
            if current_file is not None:  # Check if current_file is initialized
                hunk_header = line
                hunk_lines = []
                current_file["hunks"].append({"header": hunk_header, "lines": hunk_lines})
        elif current_file is not None and current_file["hunks"]:  # Check for both conditions
            current_file["hunks"][-1]["lines"].append(line)
    return files



def main():
    """Main function to execute the code review process."""
    pr_details = get_pr_details()
    event_data = json.load(open(os.environ["GITHUB_EVENT_PATH"], "r"))
    if event_data["action"] == "opened":
        diff = get_diff(pr_details.owner, pr_details.repo, pr_details.pull_number)
        #print("===== Diff =====:", diff)
        if not diff:
            print("No diff found")
            return

        parsed_diff = parse_diff(diff)

        exclude_patterns = os.environ.get("INPUT_EXCLUDE", "").split(",")
        print("===== exclude_patterns =====:", exclude_patterns)
        exclude_patterns = [s.strip() for s in exclude_patterns]

        filtered_diff = [
            file
            for file in parsed_diff
            if not any(fnmatch.fnmatch(file.path or "", pattern) for pattern in exclude_patterns)
        ]

        comments = analyze_code(filtered_diff, pr_details)
        if comments:
            create_review_comment(
                pr_details.owner, pr_details.repo, pr_details.pull_number, comments
            )
    elif event_data["action"] == "synchronize":
        diff = get_diff(pr_details.owner, pr_details.repo, pr_details.pull_number)
        print("===== Diff =====:", diff)
        if not diff:
            print("No diff found")
            return

        parsed_diff = parse_diff(diff)

        exclude_patterns = os.environ.get("INPUT_EXCLUDE", "").split(",")
        print("===== exclude_patterns =====:", exclude_patterns)
        exclude_patterns = [s.strip() for s in exclude_patterns]

        filtered_diff = [
            file
            for file in parsed_diff
            if not any(fnmatch.fnmatch(file.path or "", pattern) for pattern in exclude_patterns)
        ]

        comments = analyze_code(filtered_diff, pr_details)
        print("========== There are some comments on the PR ==========")
        print(comments)
        if comments:
            try:
                create_review_comment(
                    pr_details.owner, pr_details.repo, pr_details.pull_number, comments
                )
                print("***** Create-Alex-Comment *****")  # Debug print
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
