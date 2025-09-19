# Gemini Reviewer Package

This package contains the core components of the Gemini AI Code Reviewer, organized into focused, modular components.

## Package Structure

```
gemini_reviewer/
├── __init__.py           # Package initialization and exports
├── models.py             # Data models and structures
├── config.py             # Configuration management
├── github_client.py      # GitHub API client
├── gemini_client.py      # Gemini AI client
├── diff_parser.py        # Git diff parsing logic
└── code_reviewer.py      # Main orchestrator class
```

## Module Overview

### `models.py`
Contains all data structures used throughout the application:
- `PRDetails`: Pull request information
- `ReviewComment`: Code review comments
- `DiffFile`: Parsed diff file representation
- `ReviewResult`: Final review results
- And many more...

### `config.py`
Comprehensive configuration management:
- Environment-based configuration loading
- Multiple review modes (strict, standard, lenient, etc.)
- Validation and default values
- Performance tuning options

### `github_client.py`
GitHub API interactions:
- PR details and diff fetching
- Review comment creation
- Rate limiting and retry logic
- Comprehensive error handling

### `gemini_client.py`
Gemini AI integration:
- Code analysis and review generation
- Prompt engineering and optimization
- Response parsing and validation
- Token management and statistics

### `diff_parser.py`
Git diff parsing:
- Robust diff parsing with fallback mechanisms
- File filtering and size management
- Binary file detection
- Complexity analysis

### `code_reviewer.py`
Main orchestrator:
- Coordinates all components
- Implements concurrent processing
- Manages the complete review workflow
- Statistics and monitoring

## Usage

The package is designed to be used primarily through the main `CodeReviewer` class:

```python
from gemini_reviewer import Config, CodeReviewer

# Load configuration from environment
config = Config.from_environment()

# Create and use the code reviewer
with CodeReviewer(config) as reviewer:
    result = await reviewer.review_pull_request(event_path)
```

## Design Principles

1. **Modularity**: Each module has a single, well-defined responsibility
2. **Testability**: All components can be tested in isolation
3. **Configuration**: Comprehensive configuration options for any environment
4. **Error Handling**: Robust error handling with graceful degradation
5. **Performance**: Concurrent processing and resource optimization
6. **Observability**: Comprehensive logging and statistics
