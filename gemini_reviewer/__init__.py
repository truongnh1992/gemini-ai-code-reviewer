"""
Gemini AI Code Reviewer Package

A comprehensive code review system powered by Google's Gemini AI.
This package provides modular components for automated code review in GitHub pull requests.
"""

__version__ = "2.0.0"
__author__ = "truongnh1992"
__description__ = "AI-powered code review system using Google's Gemini AI"

# Import main classes for easy access
from .config import Config
from .code_reviewer import CodeReviewer, CodeReviewerError
from .models import (
    PRDetails, ReviewResult, ReviewComment, DiffFile, FileInfo, 
    HunkInfo, AnalysisContext, ProcessingStats, ReviewPriority, ReviewFocus
)

# Import client classes
from .github_client import GitHubClient, GitHubClientError
from .gemini_client import GeminiClient, GeminiClientError
from .diff_parser import DiffParser, DiffParsingError

__all__ = [
    # Main classes
    'Config',
    'CodeReviewer', 'CodeReviewerError',
    
    # Data models
    'PRDetails', 'ReviewResult', 'ReviewComment', 'DiffFile', 'FileInfo',
    'HunkInfo', 'AnalysisContext', 'ProcessingStats', 'ReviewPriority', 'ReviewFocus',
    
    # Client classes
    'GitHubClient', 'GitHubClientError',
    'GeminiClient', 'GeminiClientError', 
    'DiffParser', 'DiffParsingError',
]
