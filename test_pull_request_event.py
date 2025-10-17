#!/usr/bin/env python3
"""
Test script to validate pull_request event handling
"""

import os
import sys
import json
import tempfile

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(__file__))

def test_pull_request_event():
    """Test that pull_request events are properly handled"""
    print("Testing pull_request event handling...")
    
    # Create a mock pull_request event
    pr_event = {
        "action": "opened",
        "number": 123,
        "pull_request": {
            "number": 123,
            "title": "Test PR",
            "body": "Test description",
            "head": {
                "sha": "abc123",
                "ref": "feature-branch"
            },
            "base": {
                "sha": "def456",
                "ref": "main"
            }
        }
    }
    
    # Write to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(pr_event, f)
        event_path = f.name
    
    try:
        # Set environment variables
        os.environ['GITHUB_EVENT_NAME'] = 'pull_request'
        os.environ['GITHUB_EVENT_PATH'] = event_path
        os.environ['GITHUB_TOKEN'] = 'test_token_1234567890123456789012345678901234567890'
        os.environ['GEMINI_API_KEY'] = 'test_api_key_123456789'
        
        # Import after setting env vars
        from review_code_gemini import validate_environment, check_if_valid_trigger
        
        # Test validation
        assert validate_environment(), "Environment validation failed"
        print("✓ Environment validation passed for pull_request event")
        
        # Test trigger check
        assert check_if_valid_trigger(), "Trigger validation failed for opened action"
        print("✓ Trigger validation passed for 'opened' action")
        
        # Test synchronize action
        pr_event['action'] = 'synchronize'
        with open(event_path, 'w') as f:
            json.dump(pr_event, f)
        assert check_if_valid_trigger(), "Trigger validation failed for synchronize action"
        print("✓ Trigger validation passed for 'synchronize' action")
        
        # Test reopened action
        pr_event['action'] = 'reopened'
        with open(event_path, 'w') as f:
            json.dump(pr_event, f)
        assert check_if_valid_trigger(), "Trigger validation failed for reopened action"
        print("✓ Trigger validation passed for 'reopened' action")
        
        # Test unsupported action
        pr_event['action'] = 'closed'
        with open(event_path, 'w') as f:
            json.dump(pr_event, f)
        assert not check_if_valid_trigger(), "Trigger should not validate for closed action"
        print("✓ Trigger correctly rejected 'closed' action")
        
    finally:
        # Cleanup
        if os.path.exists(event_path):
            os.unlink(event_path)

def test_issue_comment_event():
    """Test that issue_comment events still work (backward compatibility)"""
    print("\nTesting issue_comment event handling (backward compatibility)...")
    
    # Create a mock issue_comment event
    comment_event = {
        "action": "created",
        "issue": {
            "number": 123,
            "pull_request": {
                "url": "https://api.github.com/repos/test/repo/pulls/123"
            }
        },
        "comment": {
            "body": "/gemini-review please review this PR"
        }
    }
    
    # Write to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(comment_event, f)
        event_path = f.name
    
    try:
        # Set environment variables
        os.environ['GITHUB_EVENT_NAME'] = 'issue_comment'
        os.environ['GITHUB_EVENT_PATH'] = event_path
        
        # Import after setting env vars
        from review_code_gemini import validate_environment, check_if_valid_trigger
        
        # Test validation
        assert validate_environment(), "Environment validation failed for issue_comment"
        print("✓ Environment validation passed for issue_comment event")
        
        # Test trigger check
        assert check_if_valid_trigger(), "Trigger validation failed for /gemini-review comment"
        print("✓ Trigger validation passed for /gemini-review comment")
        
        # Test without trigger keyword
        comment_event['comment']['body'] = "Just a regular comment"
        with open(event_path, 'w') as f:
            json.dump(comment_event, f)
        assert not check_if_valid_trigger(), "Trigger should not validate without /gemini-review"
        print("✓ Trigger correctly rejected comment without /gemini-review")
        
    finally:
        # Cleanup
        if os.path.exists(event_path):
            os.unlink(event_path)

def test_unsupported_event():
    """Test that unsupported events are rejected"""
    print("\nTesting unsupported event rejection...")
    
    os.environ['GITHUB_EVENT_NAME'] = 'push'
    os.environ['GITHUB_TOKEN'] = 'test_token_1234567890123456789012345678901234567890'
    os.environ['GEMINI_API_KEY'] = 'test_api_key_123456789'
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({}, f)
        os.environ['GITHUB_EVENT_PATH'] = f.name
        event_path = f.name
    
    try:
        from review_code_gemini import validate_environment
        
        assert not validate_environment(), "Should reject unsupported event type"
        print("✓ Unsupported event correctly rejected")
        
    finally:
        if os.path.exists(event_path):
            os.unlink(event_path)

if __name__ == '__main__':
    print("Testing event handling for pull_request support...\n")
    
    try:
        test_pull_request_event()
        test_issue_comment_event()
        test_unsupported_event()
        
        print("\n✅ All event handling tests passed!")
        print("\nThe action now supports:")
        print("  ✓ pull_request events (opened, synchronize, reopened)")
        print("  ✓ issue_comment events with /gemini-review trigger (backward compatible)")
        sys.exit(0)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
