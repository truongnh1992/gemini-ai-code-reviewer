import os
import requests
from utils.gemini_analyze import analyze_code

def get_pr_details(gitlab_url, project_id, mr_iid, private_token):
    headers = {"PRIVATE-TOKEN": private_token}
    pr_url = f"{gitlab_url}/api/v4/projects/{project_id}/merge_requests/{mr_iid}"
    resp = requests.get(pr_url, headers=headers)
    resp.raise_for_status()
    pr_data = resp.json()
    return pr_data["title"], pr_data["description"]

def get_diff(gitlab_url, project_id, mr_iid, private_token):
    headers = {"PRIVATE-TOKEN": private_token}
    diff_url = f"{gitlab_url}/api/v4/projects/{project_id}/merge_requests/{mr_iid}/changes"
    resp = requests.get(diff_url, headers=headers)
    resp.raise_for_status()
    diff_data = resp.json()
    # Concatenate all diffs into a single string
    diffs = []
    for change in diff_data.get("changes", []):
        diffs.append(f"diff --git a/{change['old_path']} b/{change['new_path']}\n{change['diff']}")
    return "\n".join(diffs)

def main():
    gitlab_url = os.environ.get("GITLAB_URL", "https://gitlab.com")
    project_id = os.environ["GITLAB_PROJECT_ID"]  # Numeric project ID
    mr_iid = os.environ["GITLAB_MR_IID"]  # Merge Request IID (not ID)
    private_token = os.environ["GITLAB_TOKEN"]
    gemini_api_key = os.environ["GEMINI_API_KEY"]
    output_file = "gemini_review.json"

    pr_title, pr_description = get_pr_details(gitlab_url, project_id, mr_iid, private_token)
    diff = get_diff(gitlab_url, project_id, mr_iid, private_token)

    analyze_code(
        diff=diff,
        pr_title=pr_title,
        pr_description=pr_description,
        api_key=gemini_api_key,
        output_file=output_file,
        platform="gitlab"
    )

if __name__ == "__main__":
    main()