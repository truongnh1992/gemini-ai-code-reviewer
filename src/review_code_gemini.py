import os
import json
from typing import List, Dict
import google.generativeai as client
from github import Github
from difflib import unified_diff

# Get input values from environment variables
GITHUB_TOKEN = os.environ.get('GH_TOKEN')
GEMINI_MODEL_NAME = "models/code-bison-001"  # Or another Gemini model

# Initialize GitHub and Gemini clients
gh = Github(GITHUB_TOKEN)
glm_client = client.configure(api_key=os.environ.get('GEMINI_API_KEY'))


def get_pr_details() -> Dict:
    """Retrieves details of the pull request."""
    event_path = os.environ["GITHUB_EVENT_PATH"]
    with open(event_path, "r") as f:
        event_data = json.load(f)

    print(f"Raw event data: {event_data}") # Print the raw data

    repo_name = event_data["repository"]["full_name"]
    pr_number = event_data["number"]

    print(f"Repository name: {repo_name}") # Print repo_name
    print(f"PR number: {pr_number}") # Print pr_number
    repo = gh.get_repo(repo_name)
    pr = repo.get_pull(pr_number)

    return {
        "owner": repo.owner.login,
        "repo": repo.name,
        "pull_number": pr_number,
        "title": pr.title,
        "description": pr.body,
    }


def get_diff(pr_details: Dict) -> str:
    """Fetches the diff of the pull request."""
    repo = gh.get_repo(f"{pr_details['owner']}/{pr_details['repo']}")
    pr = repo.get_pull(pr_details["pull_number"])
    return pr.get_commits().reversed[0].files[0].raw_data["patch"]


def analyze_code(
    diff: str, pr_details: Dict
) -> List[Dict[str, str]]:
    """Analyzes the code diff using Gemini and generates review comments."""
    comments = []
    diff_lines = diff.splitlines()

    # Extract changed lines for analysis
    changed_lines = []
    for line in diff_lines:
        if line.startswith('+') or line.startswith('-'):
            changed_lines.append(line)

    if not changed_lines:
        return comments

    prompt = create_prompt("\n".join(changed_lines), pr_details)
    ai_response = get_gemini_response(prompt)
    if ai_response:
        comments = create_comment(diff_lines, ai_response)
    return comments


def create_prompt(diff: str, pr_details: Dict) -> str:
    """Creates the prompt for the Gemini model."""
    return f"""Your task is to review pull requests. Instructions:
- Provide the response in following JSON format:  {{"reviews": [{{"lineNumber":  <line_number>, "reviewComment": "<review comment>"}}]}}
- Do not give positive comments or compliments.
- Provide comments and suggestions ONLY if there is something to improve, otherwise "reviews" should be an empty array.
- Write the comment in GitHub Markdown format.
- Use the given description only for the overall context and only comment the code.
- IMPORTANT: NEVER suggest adding comments to the code.

Review the following code diff and take the pull request title and description into account when writing the response.

Pull request title: {pr_details['title']}
Pull request description:

---
{pr_details['description']}
---
Git diff to review:
{diff}"""


def get_gemini_response(prompt: str) -> List[Dict[str, str]] | None:
    """Gets the AI response from the Gemini API."""
    try:
        response = glm_client.generate_text(
            model=GEMINI_MODEL_NAME,
            prompt=client.TextPrompt(text=prompt),
            temperature=0.2,
            max_output_tokens=700,
            top_p=1.0,
        )
        res = response.candidates[0].output.strip() or "{}"
        return json.loads(res).get("reviews", [])
    except Exception as e:
        print(f"Error: {e}")
        return None


def create_comment(
    diff_lines: List[str], ai_responses: List[Dict[str, str]]
) -> List[Dict[str, str]]:
    """Creates comments for the GitHub PR."""
    comments = []
    for ai_response in ai_responses:
        try:
            line_number = int(ai_response["lineNumber"])
            # Adjust line number for added lines
            for i, line in enumerate(diff_lines):
                if line.startswith('+') and i < line_number:
                    line_number += 1
            comments.append(
                {
                    "body": ai_response["reviewComment"],
                    "path": "src/review_code_gemini.py",  # Replace with actual file path
                    "line": line_number,
                }
            )
        except ValueError:
            print(f"Invalid line number: {ai_response['lineNumber']}")
    return comments


def create_review_comment(pr_details: Dict, comments: List[Dict[str, str]]):
    """Creates a review comment on the GitHub PR."""
    repo = gh.get_repo(f"{pr_details['owner']}/{pr_details['repo']}")
    pr = repo.get_pull(pr_details["pull_number"])
    pr.create_review(comments=comments, event="COMMENT")


def main():
    """Main function to run the code review process."""
    print("This is main function")
    pr_details = get_pr_details()
    diff = get_diff(pr_details)

    if not diff:
        print("No diff found")
        return

    comments = analyze_code(diff, pr_details)
    if comments:
        create_review_comment(pr_details, comments)

if __name__ == "__main__":
    main()