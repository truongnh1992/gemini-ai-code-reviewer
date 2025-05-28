import requests
import json
from typing import List, Dict, Any, Optional

def create_prompt(diff: str, pr_title: str, pr_description: str, platform: str = "generic") -> str:
    prompt = (
        f"You are an expert software engineer performing a code review for a pull/merge request on {platform}.\n"
        f"PR Title: {pr_title}\n"
        f"PR Description: {pr_description}\n"
        f"Diff:\n{diff}\n"
        "Review the code for correctness, security, performance, readability, maintainability, and adherence to best practices.\n"
        "For each issue, provide a structured JSON object with: file, line, severity (info/warning/error), category (bug, style, performance, etc.), suggestion, and rationale.\n"
        "Be concise, actionable, and professional. If no issues, reply with an empty JSON array []."
    )
    return prompt

def get_ai_response(prompt: str, api_key: str, model: str = "gemini-pro") -> List[Dict[str, Any]]:
    """
    Send the prompt to Gemini API and parse the JSON response as a list of comments.
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    response = requests.post(url, headers=headers, data=json.dumps(data), timeout=60)
    response.raise_for_status()
    try:
        candidates = response.json()["candidates"]
        content = candidates[0]["content"]["parts"][0]["text"]
        comments = json.loads(content)
        if not isinstance(comments, list):
            raise ValueError("AI response is not a list")
        return comments
    except Exception as e:
        raise RuntimeError(f"Failed to parse Gemini response: {e}")

def create_review_comment(comment: Dict[str, Any], output_file: str) -> None:
    """
    Write a single review comment to the output file in JSONL format.
    """
    with open(output_file, "a") as f:
        f.write(json.dumps(comment) + "\n")

def analyze_code(
    diff: str,
    pr_title: str,
    pr_description: str,
    api_key: str,
    output_file: str,
    platform: str = "generic",
    model: str = "gemini-pro"
) -> None:
    """
    Analyze the code diff using Gemini and write review comments to the output file.
    """
    prompt = create_prompt(diff, pr_title, pr_description, platform)
    comments = get_ai_response(prompt, api_key, model)
    for comment in comments:
        create_review_comment(comment, output_file)