import os
import json
import requests
from github import Github
from utils.gemini_analyze import analyze_code

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
OUTPUT_FILE = "gemini_review.json"

def get_pr_details(event_path):
    with open(event_path, "r") as f:
        event_data = json.load(f)
    if "issue" in event_data and "pull_request" in event_data["issue"]:
        pull_number = event_data["issue"]["number"]
        repo_full_name = event_data["repository"]["full_name"]
    else:
        pull_number = event_data["number"]
        repo_full_name = event_data["repository"]["full_name"]
    owner, repo = repo_full_name.split("/")
    return owner, repo, pull_number

def get_diff(owner, repo, pull_number):
    repo_name = f"{owner}/{repo}"
    api_url = f"https://api.github.com/repos/{repo_name}/pulls/{pull_number}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3.diff"
    }
    response = requests.get(f"{api_url}.diff", headers=headers)
    if response.status_code == 200:
        return response.text
    else:
        raise RuntimeError(f"Failed to get diff: {response.status_code} {response.text}")

def get_pr_metadata(owner, repo, pull_number):
    gh = Github(GITHUB_TOKEN)
    repo_obj = gh.get_repo(f"{owner}/{repo}")
    pr = repo_obj.get_pull(pull_number)
    return pr.title, pr.body

def main():
    event_path = os.environ["GITHUB_EVENT_PATH"]
    owner, repo, pull_number = get_pr_details(event_path)
    pr_title, pr_description = get_pr_metadata(owner, repo, pull_number)
    diff = get_diff(owner, repo, pull_number)
    analyze_code(
        diff=diff,
        pr_title=pr_title,
        pr_description=pr_description,
        api_key=GEMINI_API_KEY,
        output_file=OUTPUT_FILE,
        platform="github"
    )
    print(f"Review comments written to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()