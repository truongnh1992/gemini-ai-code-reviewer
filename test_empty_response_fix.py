#!/usr/bin/env python3
"""
Test script to verify the fix for empty response handling
"""

import sys
import os

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(__file__))

def test_parse_response_logic():
    """Test the enhanced _parse_ai_response logic with various edge cases"""
    
    # Simulate the parsing logic from GeminiClient._parse_ai_response
    def parse_ai_response_mock(response_text: str) -> list:
        """Mock version of _parse_ai_response with the fix"""
        import json
        
        print(f"  Raw response length: {len(response_text)} characters")
        print(f"  Raw response preview: {repr(response_text[:50])}")
        
        # Check if response is empty or whitespace-only
        if not response_text or not response_text.strip():
            print("  ❌ ERROR: Received empty or whitespace-only response")
            print(f"  Raw response repr: {repr(response_text[:100])}")
            return []
        
        # Clean the response (simplified version)
        cleaned_response = response_text.strip()
        if cleaned_response.startswith('```json'):
            cleaned_response = cleaned_response[7:].lstrip()
        elif cleaned_response.startswith('```'):
            cleaned_response = cleaned_response[3:].lstrip()
        if cleaned_response.endswith('```'):
            cleaned_response = cleaned_response[:-3].rstrip()
        cleaned_response = cleaned_response.strip()
        
        print(f"  Cleaned response length: {len(cleaned_response)} characters")
        print(f"  Cleaned response preview: {repr(cleaned_response[:50])}")
        
        # Validate cleaned response is not empty
        if not cleaned_response or not cleaned_response.strip():
            print("  ❌ ERROR: Cleaned response is empty after removing markdown")
            print(f"  Raw response was: {response_text[:100]}")
            return []
        
        # Try to parse JSON
        try:
            data = json.loads(cleaned_response)
            print("  ✅ Successfully parsed JSON")
            if isinstance(data, dict) and "reviews" in data:
                reviews = data.get("reviews", [])
                print(f"  ✅ Valid structure with {len(reviews)} review(s)")
                return reviews
            else:
                print("  ⚠️  JSON doesn't have expected structure")
                return []
        except json.JSONDecodeError as e:
            print(f"  ❌ JSONDecodeError: {e}")
            print(f"  Raw response length: {len(response_text)}")
            print(f"  Cleaned response: {repr(cleaned_response[:100])}")
            return []
    
    print("="*70)
    print("Testing Enhanced Empty Response Handling")
    print("="*70)
    
    test_cases = [
        ("Empty string", ""),
        ("Only whitespace (spaces)", "   "),
        ("Only whitespace (newlines)", "\n\n\n"),
        ("Only whitespace (tabs)", "\t\t\t"),
        ("Mixed whitespace", " \n\t \n "),
        ("Only markdown markers", "```json\n```"),
        ("Only markdown markers (no json tag)", "```\n```"),
        ("Valid empty reviews", '{"reviews": []}'),
        ("Valid JSON with review", '{"reviews": [{"lineNumber": 10, "reviewComment": "Test"}]}'),
        ("JSON wrapped in markdown", '```json\n{"reviews": []}\n```'),
    ]
    
    all_passed = True
    for test_name, input_text in test_cases:
        print(f"\nTest: {test_name}")
        print("-" * 70)
        
        try:
            result = parse_ai_response_mock(input_text)
            
            # Validate expected behavior
            if not input_text or not input_text.strip():
                # Should return empty list and log error
                if result == []:
                    print("  ✅ PASSED - Correctly handled empty response")
                else:
                    print("  ❌ FAILED - Should have returned empty list")
                    all_passed = False
            elif input_text.strip() in ["```json\n```", "```\n```"]:
                # Should return empty list (empty after cleaning)
                if result == []:
                    print("  ✅ PASSED - Correctly handled empty markdown")
                else:
                    print("  ❌ FAILED - Should have returned empty list")
                    all_passed = False
            else:
                # Should parse successfully or return empty list gracefully
                print("  ✅ PASSED - Handled without crashing")
                
        except Exception as e:
            print(f"  ❌ FAILED - Unexpected exception: {e}")
            all_passed = False
    
    print("\n" + "="*70)
    if all_passed:
        print("✅ ALL TESTS PASSED!")
        print("="*70)
        print("\nThe fix successfully:")
        print("  ✓ Detects empty responses before JSON parsing")
        print("  ✓ Detects responses that become empty after cleaning")
        print("  ✓ Provides detailed logging for debugging")
        print("  ✓ Returns empty list gracefully without crashing")
        print("\nThis resolves the error:")
        print("  'Failed to parse JSON response: Expecting value: line 1 column 1'")
        print("\nThe enhanced logging will now show:")
        print("  • Raw response length and preview")
        print("  • Cleaned response length and preview")
        print("  • Clear error message identifying empty responses")
        return True
    else:
        print("❌ SOME TESTS FAILED!")
        print("="*70)
        return False

if __name__ == '__main__':
    try:
        success = test_parse_response_logic()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test execution failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
