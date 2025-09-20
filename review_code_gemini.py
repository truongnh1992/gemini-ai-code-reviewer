#!/usr/bin/env python3
"""
Gemini AI Code Reviewer - Main Entry Point

A GitHub Action that automatically reviews pull requests using Google's Gemini AI.
This is the main entry point that orchestrates the entire review process.
"""

import asyncio
import logging
import logging.handlers
import os
import sys
from typing import Optional

from gemini_reviewer import Config, CodeReviewer, CodeReviewerError, ReviewResult


def setup_logging_from_config(config: Config):
    """Set up logging based on configuration."""
    log_handlers = [logging.StreamHandler(sys.stdout)]
    
    # Add file handler if enabled
    if config.logging.enable_file_logging:
        try:
            file_handler = logging.handlers.RotatingFileHandler(
                config.logging.log_file_path,
                maxBytes=config.logging.max_log_size,
                backupCount=config.logging.backup_count
            )
            log_handlers.append(file_handler)
        except Exception as e:
            print(f"Warning: Could not setup file logging: {e}")
    
    logging.basicConfig(
        level=getattr(logging, config.logging.level.value),
        format=config.logging.format,
        handlers=log_handlers
    )
    
    # Set specific log levels for external libraries
    logging.getLogger('github').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('google').setLevel(logging.WARNING)


def validate_environment() -> bool:
    """Validate that all required environment variables are present."""
    required_vars = ["GITHUB_TOKEN", "GEMINI_API_KEY", "GITHUB_EVENT_PATH"]
    missing_vars = []
    
    for var in required_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
        return False
    
    # Validate event name
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    if event_name != "issue_comment":
        print(f"Error: Unsupported GitHub event: {event_name}. Only 'issue_comment' is supported.")
        return False
    
    return True


def check_if_comment_trigger() -> bool:
    """Check if this was triggered by a comment with the review command."""
    import json
    
    try:
        with open(os.environ["GITHUB_EVENT_PATH"], "r") as f:
            event_data = json.load(f)
        
        # Check if it's a comment on a PR
        if not event_data.get("issue", {}).get("pull_request"):
            print("Info: Comment was not on a pull request, skipping review.")
            return False
        
        # Check if comment contains the review trigger
        comment_body = event_data.get("comment", {}).get("body", "").lower()
        if "/gemini-review" not in comment_body:
            print("Info: Comment does not contain '/gemini-review' trigger, skipping review.")
            return False
        
        return True
        
    except Exception as e:
        print(f"Error: Could not process GitHub event data: {e}")
        return False


async def main_async() -> int:
    """Main async function for the code review process."""
    print("🤖 Gemini AI Code Reviewer Starting...")
    
    # Validate environment first
    if not validate_environment():
        return 1
    
    # Check if this is a valid trigger
    if not check_if_comment_trigger():
        return 0  # Not an error, just not our trigger
    
    try:
        # Load configuration from environment
        config = Config.from_environment()
        
        # Setup logging based on configuration
        setup_logging_from_config(config)
        logger = logging.getLogger(__name__)
        
        logger.info("=== Gemini AI Code Reviewer Started ===")
        logger.info(f"Configuration loaded: {config.to_dict()}")
        
        # Create code reviewer with configuration
        with CodeReviewer(config) as reviewer:
            
            # Test connections to external services
            logger.info("Testing connections to external services...")
            connections = reviewer.test_connections()
            
            failed_connections = [service for service, status in connections.items() if not status]
            if failed_connections:
                logger.error(f"Failed connections: {failed_connections}")
                return 1
            
            logger.info("✅ All external service connections are working")
            
            # Perform the code review
            result = await reviewer.review_pull_request(os.environ["GITHUB_EVENT_PATH"])
            
            # Log results
            await _log_review_results(result, reviewer)
            
            # Return appropriate exit code
            if result.errors:
                logger.error(f"Review completed with {len(result.errors)} errors")
                for error in result.errors:
                    logger.error(f"  - {error}")
                return 1
            else:
                logger.info("✅ Review completed successfully")
                return 0
    
    except Exception as e:
        print(f"❌ Fatal error during code review: {str(e)}")
        logging.exception("Fatal error details:")
        return 1


async def _log_review_results(result: ReviewResult, reviewer: CodeReviewer):
    """Log comprehensive review results."""
    logger = logging.getLogger(__name__)
    
    # Basic results
    logger.info("=== Review Results ===")
    logger.info(f"PR: #{result.pr_details.pull_number} - {result.pr_details.title}")
    logger.info(f"Files processed: {result.processed_files}")
    logger.info(f"Comments generated: {result.total_comments}")
    processing_time = result.processing_time or 0.0
    logger.info(f"Processing time: {processing_time:.2f}s")
    
    # Comment breakdown by priority
    if result.comments:
        priority_counts = result.comments_by_priority
        logger.info("Comment breakdown by priority:")
        for priority, count in priority_counts.items():
            if count > 0:
                emoji = {"critical": "🚨", "high": "⚠️", "medium": "💡", "low": "ℹ️"}.get(priority.value, "📝")
                logger.info(f"  {emoji} {priority.value.title()}: {count}")
    
    # Detailed statistics
    stats = reviewer.get_statistics()
    logger.debug("=== Detailed Statistics ===")
    logger.debug(f"Processing stats: {stats.get('processing', {})}")
    logger.debug(f"GitHub stats: {stats.get('github', {})}")
    logger.debug(f"Gemini stats: {stats.get('gemini', {})}")
    logger.debug(f"Parsing stats: {stats.get('parsing', {})}")
    
    # Errors
    if result.errors:
        logger.warning(f"Errors encountered: {len(result.errors)}")
        for error in result.errors:
            logger.warning(f"  - {error}")


def main() -> int:
    """Main synchronous entry point."""
    try:
        return asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n⚠️  Review interrupted by user")
        return 130  # Standard exit code for Ctrl+C
    except Exception as e:
        print(f"❌ Fatal error: {str(e)}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)