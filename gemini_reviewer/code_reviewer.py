"""
Main code reviewer orchestrator for the Gemini AI Code Reviewer.

This module contains the main CodeReviewer class that coordinates all components
and implements concurrent processing for improved performance.
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional

from .config import Config
from .models import (
    PRDetails, ReviewResult, ReviewComment, DiffFile, HunkInfo,
    AnalysisContext, ProcessingStats, ReviewPriority
)
from .github_client import GitHubClient, GitHubClientError
from .gemini_client import GeminiClient, GeminiClientError
from .diff_parser import DiffParser, DiffParsingError


logger = logging.getLogger(__name__)


class CodeReviewerError(Exception):
    """Base exception for code reviewer errors."""
    pass


class CodeReviewer:
    """Main orchestrator class for the code review process."""
    
    def __init__(self, config: Config):
        """Initialize the code reviewer with configuration."""
        self.config = config
        
        # Initialize components
        self.github_client = GitHubClient(config.github)
        self.gemini_client = GeminiClient(config.gemini)
        self.diff_parser = DiffParser()
        
        # Statistics tracking
        self.stats = ProcessingStats(start_time=time.time())
        
        logger.info("Initialized CodeReviewer with all components")
    
    async def review_pull_request(self, event_path: str) -> ReviewResult:
        """Main entry point for reviewing a pull request."""
        logger.info("=== Starting Pull Request Review ===")
        
        try:
            # Extract PR details from GitHub event
            pr_details = self.github_client.get_pr_details_from_event(event_path)
            logger.info(f"Reviewing PR #{pr_details.pull_number}: {pr_details.title}")
            
            # Create initial result object
            result = ReviewResult(pr_details=pr_details)
            
            # Get and parse diff
            diff_content = await self._get_pr_diff(pr_details)
            if not diff_content:
                result.errors.append("Failed to retrieve PR diff")
                return result
            
            # Parse diff into structured format
            diff_files = await self._parse_diff(diff_content)
            if not diff_files:
                result.errors.append("No files found in PR diff")
                return result
            
            # Filter files based on configuration
            filtered_files = await self._filter_files(diff_files)
            if not filtered_files:
                result.errors.append("No files remaining after filtering")
                return result
            
            result.processed_files = len(filtered_files)
            logger.info(f"Processing {len(filtered_files)} files for review")
            
            # Analyze files and generate comments
            if self.config.performance.enable_concurrent_processing:
                comments = await self._analyze_files_concurrently(filtered_files, pr_details)
            else:
                comments = await self._analyze_files_sequentially(filtered_files, pr_details)
            
            result.comments = comments
            
            # Create review on GitHub if we have comments
            if comments:
                success = await self._create_github_review(pr_details, comments)
                if not success:
                    result.errors.append("Failed to create GitHub review")
            else:
                logger.info("No comments generated - code looks good! 👍")
            
            # Finalize statistics
            self.stats.end_time = time.time()
            result.processing_time = self.stats.duration
            
            logger.info(f"✅ Review completed in {result.processing_time:.2f}s with {len(comments)} comments")
            return result
            
        except Exception as e:
            logger.error(f"Error during PR review: {str(e)}")
            result = ReviewResult(pr_details=PRDetails("", "", 0, "", ""))
            result.errors.append(str(e))
            return result
    
    async def _get_pr_diff(self, pr_details: PRDetails) -> str:
        """Get PR diff with error handling."""
        try:
            logger.info("Fetching PR diff...")
            diff_content = self.github_client.get_pr_diff(
                pr_details.owner, pr_details.repo, pr_details.pull_number
            )
            logger.debug(f"Retrieved diff with {len(diff_content)} characters")
            return diff_content
        except GitHubClientError as e:
            logger.error(f"Failed to get PR diff: {str(e)}")
            return ""
    
    async def _parse_diff(self, diff_content: str) -> List[DiffFile]:
        """Parse diff content with error handling."""
        try:
            logger.info("Parsing diff content...")
            diff_files = self.diff_parser.parse_diff(diff_content)
            
            # Log parsing statistics
            stats = self.diff_parser.get_parsing_statistics()
            logger.info(f"Parsed {stats['parsed_files']} files, "
                       f"skipped {stats['skipped_files']} files")
            
            return diff_files
        except DiffParsingError as e:
            logger.error(f"Failed to parse diff: {str(e)}")
            return []
    
    async def _filter_files(self, diff_files: List[DiffFile]) -> List[DiffFile]:
        """Filter files based on configuration."""
        logger.info("Filtering files based on configuration...")
        
        # Apply basic filtering
        filtered_files = self.diff_parser.filter_files(
            diff_files,
            exclude_patterns=self.config.review.exclude_patterns,
            max_files=self.config.review.max_files_per_review,
            min_changes=self.config.review.min_line_changes
        )
        
        # Filter large hunks to manage token usage
        filtered_files = self.diff_parser.filter_large_hunks(
            filtered_files,
            max_lines_per_hunk=self.config.review.max_lines_per_hunk,
            max_hunks_per_file=self.config.review.max_hunks_per_file
        )
        
        # Additional filtering based on configuration
        final_files = []
        for diff_file in filtered_files:
            if self.config.should_review_file(diff_file.file_info.path):
                final_files.append(diff_file)
            else:
                logger.debug(f"Skipping file due to config: {diff_file.file_info.path}")
        
        logger.info(f"Filtered down to {len(final_files)} files for review")
        return final_files
    
    async def _analyze_files_sequentially(
        self, 
        diff_files: List[DiffFile], 
        pr_details: PRDetails
    ) -> List[ReviewComment]:
        """Analyze files sequentially."""
        logger.info("Analyzing files sequentially...")
        
        all_comments = []
        
        for i, diff_file in enumerate(diff_files):
            logger.info(f"Analyzing file {i+1}/{len(diff_files)}: {diff_file.file_info.path}")
            
            try:
                file_comments = await self._analyze_single_file(diff_file, pr_details)
                all_comments.extend(file_comments)
                self.stats.files_processed += 1
                
            except Exception as e:
                logger.error(f"Error analyzing file {diff_file.file_info.path}: {str(e)}")
                self.stats.errors_encountered += 1
                continue
        
        return all_comments
    
    async def _analyze_files_concurrently(
        self, 
        diff_files: List[DiffFile], 
        pr_details: PRDetails
    ) -> List[ReviewComment]:
        """Analyze files concurrently for improved performance."""
        logger.info(f"Analyzing {len(diff_files)} files concurrently "
                   f"(max workers: {self.config.performance.max_concurrent_files})")
        
        all_comments = []
        
        # Process files in chunks to manage resources
        chunk_size = self.config.performance.chunk_size
        max_workers = min(self.config.performance.max_concurrent_files, len(diff_files))
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all file analysis tasks
            future_to_file = {
                executor.submit(self._analyze_single_file_sync, diff_file, pr_details): diff_file
                for diff_file in diff_files
            }
            
            # Process completed tasks as they finish
            for future in as_completed(future_to_file):
                diff_file = future_to_file[future]
                
                try:
                    file_comments = future.result()
                    all_comments.extend(file_comments)
                    self.stats.files_processed += 1
                    
                    logger.debug(f"Completed analysis of {diff_file.file_info.path} "
                               f"({len(file_comments)} comments)")
                    
                except Exception as e:
                    logger.error(f"Error analyzing file {diff_file.file_info.path}: {str(e)}")
                    self.stats.errors_encountered += 1
        
        logger.info(f"Concurrent analysis completed: {len(all_comments)} total comments")
        return all_comments
    
    def _analyze_single_file_sync(self, diff_file: DiffFile, pr_details: PRDetails) -> List[ReviewComment]:
        """Synchronous wrapper for analyzing a single file (for thread pool)."""
        return asyncio.run(self._analyze_single_file(diff_file, pr_details))
    
    async def _analyze_single_file(self, diff_file: DiffFile, pr_details: PRDetails) -> List[ReviewComment]:
        """Analyze a single file and return review comments."""
        file_path = diff_file.file_info.path
        logger.debug(f"Starting analysis of {file_path}")
        
        file_comments = []
        
        # Create analysis context
        context = AnalysisContext(
            pr_details=pr_details,
            file_info=diff_file.file_info,
            language=self.diff_parser.get_file_language(file_path)
        )
        
        # Get prompt template based on configuration
        prompt_template = self.config.get_review_prompt_template()
        
        # Analyze each hunk in the file
        for hunk_index, hunk in enumerate(diff_file.hunks):
            try:
                logger.debug(f"Analyzing hunk {hunk_index+1}/{len(diff_file.hunks)} in {file_path}")
                
                # Get AI analysis for this hunk
                ai_responses = self.gemini_client.analyze_code_hunk(
                    hunk, context, prompt_template
                )
                
                self.stats.api_calls_made += 1
                
                # Convert AI responses to review comments
                for ai_response in ai_responses:
                    comment = self._convert_to_review_comment(
                        ai_response, diff_file, hunk, hunk_index
                    )
                    if comment:
                        file_comments.append(comment)
                
            except GeminiClientError as e:
                logger.warning(f"AI analysis failed for hunk {hunk_index+1} in {file_path}: {str(e)}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error analyzing hunk in {file_path}: {str(e)}")
                continue
        
        logger.debug(f"Generated {len(file_comments)} comments for {file_path}")
        return file_comments
    
    def _convert_to_review_comment(
        self,
        ai_response,
        diff_file: DiffFile,
        hunk: HunkInfo,
        hunk_index: int
    ) -> Optional[ReviewComment]:
        """Convert AI response to GitHub review comment."""
        try:
            # Calculate the position in the diff for GitHub API
            # This is a simplified calculation - in a real implementation,
            # you'd need to properly map line numbers to diff positions
            position = ai_response.line_number
            
            # Ensure position is within hunk bounds
            if position < 1 or position > len(hunk.lines):
                logger.warning(f"Line number {position} is outside hunk range")
                return None
            
            comment = ReviewComment(
                body=ai_response.review_comment,
                path=diff_file.file_info.path,
                position=position,
                line_number=ai_response.line_number,
                priority=ai_response.priority,
                category=ai_response.category
            )
            
            return comment
            
        except Exception as e:
            logger.warning(f"Error converting AI response to comment: {str(e)}")
            return None
    
    async def _create_github_review(self, pr_details: PRDetails, comments: List[ReviewComment]) -> bool:
        """Create GitHub review with comments."""
        try:
            logger.info(f"Creating GitHub review with {len(comments)} comments...")
            
            # Filter comments by priority if configured
            filtered_comments = self._filter_comments_by_priority(comments)
            
            if not filtered_comments:
                logger.info("No comments meet priority threshold")
                return True
            
            success = self.github_client.create_review(pr_details, filtered_comments)
            if success:
                logger.info("✅ Successfully created GitHub review")
            
            return success
            
        except GitHubClientError as e:
            logger.error(f"Failed to create GitHub review: {str(e)}")
            return False
    
    def _filter_comments_by_priority(self, comments: List[ReviewComment]) -> List[ReviewComment]:
        """Filter comments based on priority threshold."""
        if not comments:
            return []
        
        priority_order = {
            ReviewPriority.CRITICAL: 4,
            ReviewPriority.HIGH: 3,
            ReviewPriority.MEDIUM: 2,
            ReviewPriority.LOW: 1
        }
        
        threshold_value = priority_order.get(self.config.review.priority_threshold, 1)
        
        filtered_comments = []
        for comment in comments:
            comment_value = priority_order.get(comment.priority, 1)
            if comment_value >= threshold_value:
                filtered_comments.append(comment)
        
        if len(filtered_comments) != len(comments):
            logger.info(f"Filtered {len(comments)} comments to {len(filtered_comments)} "
                       f"based on priority threshold ({self.config.review.priority_threshold.value})")
        
        return filtered_comments
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive processing statistics."""
        github_stats = {}
        gemini_stats = self.gemini_client.get_statistics()
        parsing_stats = self.diff_parser.get_parsing_statistics()
        
        try:
            rate_limit = self.github_client.check_rate_limit()
            github_stats = rate_limit.get('core', {})
        except Exception:
            pass
        
        return {
            'processing': {
                'duration': self.stats.duration,
                'files_processed': self.stats.files_processed,
                'files_skipped': self.stats.files_skipped,
                'api_calls_made': self.stats.api_calls_made,
                'errors_encountered': self.stats.errors_encountered,
                'processing_rate': self.stats.processing_rate
            },
            'github': github_stats,
            'gemini': gemini_stats,
            'parsing': parsing_stats
        }
    
    def test_connections(self) -> Dict[str, bool]:
        """Test connections to external services."""
        logger.info("Testing connections to external services...")
        
        results = {}
        
        # Test GitHub connection
        try:
            # Test by getting rate limit info - if this works, connection is OK
            rate_limit = self.github_client.check_rate_limit()
            
            # If we got any rate limit response, connection is working
            if rate_limit and 'core' in rate_limit:
                results['github'] = True
                remaining = rate_limit.get('core', {}).get('remaining', 'unknown')
                
                # Try to get additional user info for better logging
                try:
                    user = self.github_client._client.get_user()
                    github_user = user.login if user else "unknown"
                    logger.info(f"✅ GitHub connection: OK (user: {github_user}, remaining: {remaining})")
                except Exception:
                    # User info failed, but connection is still OK based on rate limit check
                    logger.info(f"✅ GitHub connection: OK (remaining: {remaining})")
            else:
                # Rate limit check didn't return expected structure
                raise Exception("Rate limit check returned unexpected structure")
                    
        except Exception as e:
            results['github'] = False
            logger.error(f"❌ GitHub connection failed: {str(e)}")
        
        # Test Gemini connection
        try:
            results['gemini'] = self.gemini_client.test_connection()
            if results['gemini']:
                logger.info("✅ Gemini connection: OK")
            else:
                logger.error("❌ Gemini connection failed")
        except Exception as e:
            results['gemini'] = False
            logger.error(f"❌ Gemini connection error: {str(e)}")
        
        return results
    
    def close(self):
        """Clean up resources."""
        logger.info("Cleaning up CodeReviewer resources...")
        
        try:
            self.github_client.close()
            self.gemini_client.close()
        except Exception as e:
            logger.warning(f"Error during cleanup: {str(e)}")
        
        logger.info("CodeReviewer cleanup completed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
