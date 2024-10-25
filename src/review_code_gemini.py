import os
import json
from typing import List, Dict

from google.ai import generativelanguage as glm
from google.generativeai import client
from github import Github
from unidiff import PatchSet
from wcmatch import wcmatch

# Get input values from environment variables
GH_TOKEN = os.environ["GH_TOKEN"]
GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]  # Replace with your Google API key
GEMINI_MODEL_NAME = "models/code-bison-001"  # Or another Gemini model

# Initialize GitHub and Gemini clients
gh = Github(GH_TOKEN)
glm_client = client.GenerativeServiceClient.from_api_key(api_key=GOOGLE_API_KEY)


def get_pr_details() -> Dict:
    """Retrieves details of the pull request."""
    event_path = os.environ["GITHUB_EVENT_PATH"]
    with open(event_path, "r") as f:
        event_data = json.load(f)

    repo_name = event_data["repository"]["full_name"]
    pr_number = event_data["number"]
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
    parsed_diff: List, pr_details: Dict
) -> List[Dict[str, str]]:
    """Analyzes the code diff using Gemini and generates review comments."""
    comments = []

    for file in parsed_diff:
        if file.to == "/dev/null":
            continue  # Ignore deleted files
        for chunk in file.chunks:
            prompt = create_prompt(file, chunk, pr_details)
            ai_response = get_gemini_response(prompt)
            if ai_response:
                new_comments = create_comment(file, chunk, ai_response)
                if new_comments:
                    comments.extend(new_comments)
    return comments


def create_prompt(file, chunk, pr_details: Dict) -> str:
    """Creates the prompt for the Gemini model."""
    # You might need to adjust the prompt slightly for Gemini
    return f"""Your task is to review pull requests. Instructions:
- Provide the response in following JSON format:  {{"reviews": [{{"lineNumber":  <line_number>, "reviewComment": "<review comment>"}}]}}
- Do not give positive comments or compliments.
- Provide comments and suggestions ONLY if there is something to improve, otherwise "reviews" should be an empty array.
- Write the comment in GitHub Markdown format.
- Use the given description only for the overall context and only comment the code.
- IMPORTANT: NEVER suggest adding comments to the code.

Review the following code diff in the file "{file.to}" and take the pull request title and description into account when writing the response.

Pull request title: {pr_details['title']}
Pull request description:

---
{pr_details['description']}
---
Git diff to review:
{chunk.content}"""


def get_gemini_response(prompt: str) -> List[Dict[str, str]] | None:
    """Gets the AI response from the Gemini API."""
    try:
        response = glm_client.generate_text(
            model=GEMINI_MODEL_NAME,
            prompt=glm.TextPrompt(text=prompt),
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
    file, chunk, ai_responses: List[Dict[str, str]]
) -> List[Dict[str, str]]:
    """Creates comments for the GitHub PR."""
    comments = []
    for ai_response in ai_responses:
        try:
            line_number = int(ai_response["lineNumber"])
            # Adjust line number based on diff chunk
            for change in chunk.changes:
                if change.add and change.line_number:
                    if line_number >= change.line_number:
                        line_number += chunk.new_start - 1
                        break
            comments.append(
                {
                    "body": ai_response["reviewComment"],
                    "path": file.to,
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

    parsed_diff = PatchSet(diff)  # Use unidiff

    exclude_patterns = os.environ.get("INPUT_EXCLUDE", "").split(",")
    exclude_patterns = [p.strip() for p in exclude_patterns if p.strip()]

    filtered_diff = [
        file
        for file in parsed_diff
        if not any(wcmatch.fnmatch(file.path, p) for p in exclude_patterns)  # Use wcmatch
    ]

    comments = analyze_code(filtered_diff, pr_details)
    if comments:
        create_review_comment(pr_details, comments)

if __name__ == "__main__":
    main()