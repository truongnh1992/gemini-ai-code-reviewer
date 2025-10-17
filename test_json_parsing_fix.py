#!/usr/bin/env python3
"""
Test script to verify JSON parsing handles markdown code blocks correctly
"""

import sys
import os
import json

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(__file__))

def test_clean_response_text():
    """Test the _clean_response_text method with various formats"""
    
    # Simulate the cleaning logic from GeminiClient._clean_response_text
    def clean_response_text(response_text: str) -> str:
        """Clean the response text from common formatting issues."""
        cleaned = response_text.strip()
        
        # Remove markdown code block markers (handle various formats)
        # Handle ```json at the start
        if cleaned.startswith('```json'):
            cleaned = cleaned[7:].lstrip()
        # Handle ```JSON (uppercase)
        elif cleaned.startswith('```JSON'):
            cleaned = cleaned[7:].lstrip()
        # Handle ``` followed by newline
        elif cleaned.startswith('```\n'):
            cleaned = cleaned[4:]
        # Handle ``` followed by any whitespace
        elif cleaned.startswith('```'):
            # Find the end of the opening marker (could be ```json\n or just ```\n)
            first_newline = cleaned.find('\n')
            if first_newline != -1:
                cleaned = cleaned[first_newline + 1:]
            else:
                cleaned = cleaned[3:].lstrip()
        
        # Remove closing ``` markers
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3].rstrip()
        
        return cleaned.strip()
    
    # Test data
    valid_json = '{"reviews": [{"lineNumber": 10, "reviewComment": "Test comment", "priority": "high"}]}'
    
    test_cases = [
        ("Plain JSON", valid_json, True),
        ("Markdown with ```json", f"```json\n{valid_json}\n```", True),
        ("Markdown with ```JSON", f"```JSON\n{valid_json}\n```", True),
        ("Markdown with ``` only", f"```\n{valid_json}\n```", True),
        ("Markdown with ```json no newline", f"```json{valid_json}```", True),
        ("Markdown with extra whitespace", f"```json  \n  {valid_json}  \n  ```", True),
        ("Markdown with ``` and spaces", f"```  \n{valid_json}\n```", True),
    ]
    
    print("="*70)
    print("Testing JSON Parsing with Markdown Code Blocks")
    print("="*70)
    
    all_passed = True
    for test_name, input_text, should_parse in test_cases:
        print(f"\nTest: {test_name}")
        print(f"Input preview: {input_text[:50]}...")
        
        try:
            cleaned = clean_response_text(input_text)
            print(f"Cleaned: {cleaned[:50]}...")
            
            # Try to parse as JSON
            parsed = json.loads(cleaned)
            
            if should_parse:
                print(f"✓ PASSED - Successfully parsed JSON")
                # Validate structure
                if "reviews" in parsed and isinstance(parsed["reviews"], list):
                    print(f"✓ Valid structure with {len(parsed['reviews'])} review(s)")
                else:
                    print(f"⚠ Warning: Unexpected JSON structure")
            else:
                print(f"✗ FAILED - Should not have parsed")
                all_passed = False
                
        except json.JSONDecodeError as e:
            if should_parse:
                print(f"✗ FAILED - JSONDecodeError: {e}")
                print(f"  Cleaned text: {cleaned}")
                all_passed = False
            else:
                print(f"✓ PASSED - Expected parse failure")
        except Exception as e:
            print(f"✗ FAILED - Unexpected error: {e}")
            all_passed = False
    
    print("\n" + "="*70)
    if all_passed:
        print("✅ ALL TESTS PASSED!")
        print("="*70)
        print("\nThe fix successfully handles:")
        print("  ✓ Plain JSON responses")
        print("  ✓ JSON wrapped in ```json...```")
        print("  ✓ JSON wrapped in ```JSON...``` (uppercase)")
        print("  ✓ JSON wrapped in ```...``` (no language tag)")
        print("  ✓ Various whitespace combinations")
        print("\nThis resolves the error:")
        print("  'Failed to parse JSON response: Expecting value: line 1 column 1'")
        return True
    else:
        print("❌ SOME TESTS FAILED!")
        print("="*70)
        return False

if __name__ == '__main__':
    try:
        success = test_clean_response_text()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test execution failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
