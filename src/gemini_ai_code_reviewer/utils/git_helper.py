
import json
from typing import Any, Dict, List

from unidiff import Hunk

from models.pr_detail import FileInfo

EXCLUDE_PATTERN_DEFAULT = '*.md,*.txt,package-lock.json,pubspec.yaml,*.g.dart,*.freezed.dart,*.gr.dart,*.json,*.graphql'

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

def create_comment(file: FileInfo, hunk: Hunk, ai_responses: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Creates comment objects from AI responses."""
    # print("AI responses in create_comment:", ai_responses)
    # print(f"Hunk details - start: {hunk.source_start}, length: {hunk.source_length}")
    # print(f"Hunk content:\n{hunk.content}")
    
    comments = []
    for ai_response in ai_responses:
        try:
            line_number = int(ai_response["lineNumber"])
            # print(f"Original AI suggested line: {line_number}")
            
            # Ensure the line number is within the hunk's range
            if line_number < 1 or line_number > hunk.source_length:
                print(f"Warning: Line number {line_number} is outside hunk range")
                continue
                
            comment = {
                "body": ai_response["reviewComment"],
                "path": file.path,
                "position": line_number
            }
            # print(f"Created comment: {json.dumps(comment, indent=2)}")
            comments.append(comment)
            
        except (KeyError, TypeError, ValueError) as e:
            print(f"Error creating comment from AI response: {e}, Response: {ai_response}")
    return comments


