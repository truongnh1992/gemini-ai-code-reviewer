class PRDetails:
    def __init__(self, owner: str, repo: str, pull_number: int, title: str, description: str,source_branch: str, target_branch: str):
        self.owner = owner
        self.repo = repo
        self.pull_number = pull_number
        self.title = title
        self.description = description
        self.source_branch = source_branch
        self.target_branch = target_branch
class FileInfo:
    """Simple class to hold file information."""
    def __init__(self, path: str):
        self.path = path

