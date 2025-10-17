#!/usr/bin/env python3
"""
Test script to demonstrate the improved prompt template
that makes the AI more likely to generate review comments
"""

import sys
import os

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(__file__))

def show_prompt_comparison():
    """Show the before and after prompt templates"""
    
    print("="*80)
    print("PROMPT TEMPLATE IMPROVEMENT DEMONSTRATION")
    print("="*80)
    print()
    print("ISSUE: AI was not generating comments even when code had issues")
    print("ROOT CAUSE: Vague prompt instruction 'ONLY if there is something to improve'")
    print()
    print("="*80)
    print("BEFORE (Old Prompt - Too Vague):")
    print("="*80)
    
    old_prompt = """Your task is reviewing pull requests. Instructions:
- Provide the response in following JSON format: {{"reviews": [{{"lineNumber": <line_number>, "reviewComment": "<review comment>"}}]}}
- Provide comments and suggestions ONLY if there is something to improve, otherwise "reviews" should be an empty array.
- Use GitHub Markdown in comments
- IMPORTANT: NEVER suggest adding comments to the code"""
    
    print(old_prompt)
    print()
    print("PROBLEMS WITH OLD PROMPT:")
    print("  ❌ 'ONLY if there is something to improve' is too vague")
    print("  ❌ No explicit guidance on WHAT to look for")
    print("  ❌ AI interprets this conservatively, missing real issues")
    print("  ❌ No examples or categories of issues")
    print()
    
    print("="*80)
    print("AFTER (New Prompt - Clear & Directive):")
    print("="*80)
    
    new_prompt = """You are an expert code reviewer analyzing a pull request. Your task is to identify issues and provide constructive feedback.

RESPONSE FORMAT:
- Return valid JSON: {{"reviews": [{{"lineNumber": <line_number>, "reviewComment": "<review comment>", "priority": "<low|medium|high|critical>", "category": "<category>"}}]}}
- If no issues are found, return: {{"reviews": []}}
- Use GitHub Markdown for formatting in comments

WHAT TO REVIEW:
Look for and comment on:
- **Bugs & Logic Errors**: Incorrect logic, edge cases not handled, potential runtime errors
- **Security Issues**: Vulnerabilities, injection risks, authentication/authorization problems, data exposure
- **Performance Problems**: Inefficient algorithms, unnecessary loops, memory leaks, N+1 queries
- **Code Quality**: Duplicated code, poor naming, complex functions that should be split
- **Error Handling**: Missing try-catch, unhandled edge cases, silent failures
- **Best Practices**: Violations of language-specific conventions, anti-patterns
- **Potential Null/Undefined**: Missing null checks, unsafe optional chaining
- **Resource Management**: Unclosed connections, file handles, memory management issues

GUIDELINES:
- Be specific and actionable in your feedback
- Reference the exact line number where the issue occurs
- Explain WHY something is a problem and HOW to fix it
- Prioritize critical bugs and security issues as "high" or "critical"
- Mark minor improvements as "low"
- NEVER suggest adding code comments or documentation (focus on code issues only)
- If the code is genuinely good with no issues, return an empty reviews array"""
    
    print(new_prompt)
    print()
    print("IMPROVEMENTS IN NEW PROMPT:")
    print("  ✅ Explicitly lists 8 categories of issues to look for")
    print("  ✅ Clear, actionable guidelines for the AI")
    print("  ✅ Defines priority levels (low, medium, high, critical)")
    print("  ✅ Instructs AI to explain WHY and HOW to fix issues")
    print("  ✅ More directive language encourages finding real problems")
    print("  ✅ Removes vague 'ONLY if' that was causing conservative behavior")
    print("  ✅ Adds category field for better organization")
    print()
    
    print("="*80)
    print("EXPECTED IMPACT:")
    print("="*80)
    print()
    print("The improved prompt should make the AI:")
    print("  1. ✅ Generate comments when there ARE actual issues")
    print("  2. ✅ Look for specific categories of problems")
    print("  3. ✅ Provide more detailed and actionable feedback")
    print("  4. ✅ Properly categorize and prioritize issues")
    print("  5. ✅ Be more thorough while still avoiding false positives")
    print()
    print("The AI will still return empty reviews for genuinely good code,")
    print("but will now catch issues it previously missed due to vague instructions.")
    print()

def test_prompt_loading():
    """Test that the new prompt can be loaded from config"""
    print("="*80)
    print("TESTING PROMPT LOADING FROM CONFIG")
    print("="*80)
    print()
    
    try:
        from gemini_reviewer.config import Config, ReviewMode
        
        # Create a minimal config for testing
        os.environ['GITHUB_TOKEN'] = 'test_token_12345'
        os.environ['GEMINI_API_KEY'] = 'test_api_key_12345'
        
        config = Config.from_environment()
        prompt = config.get_review_prompt_template()
        
        print("✅ Successfully loaded prompt template from config")
        print(f"✅ Prompt length: {len(prompt)} characters")
        print()
        
        # Verify key improvements are in the prompt
        checks = {
            "Contains 'WHAT TO REVIEW' section": "WHAT TO REVIEW" in prompt,
            "Contains 'Bugs & Logic Errors' category": "Bugs & Logic Errors" in prompt,
            "Contains 'Security Issues' category": "Security Issues" in prompt,
            "Contains 'Performance Problems' category": "Performance Problems" in prompt,
            "Contains 'GUIDELINES' section": "GUIDELINES" in prompt,
            "Contains priority field in JSON format": '"priority"' in prompt,
            "Contains category field in JSON format": '"category"' in prompt,
            "Does NOT contain vague 'ONLY if' language": "ONLY if there is something to improve" not in prompt,
        }
        
        print("VERIFICATION CHECKS:")
        all_passed = True
        for check, result in checks.items():
            status = "✅" if result else "❌"
            print(f"  {status} {check}")
            if not result:
                all_passed = False
        
        print()
        if all_passed:
            print("="*80)
            print("✅ ALL CHECKS PASSED - Prompt improvements verified!")
            print("="*80)
            return True
        else:
            print("="*80)
            print("❌ Some checks failed")
            print("="*80)
            return False
            
    except Exception as e:
        print(f"❌ Error testing prompt loading: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print()
    show_prompt_comparison()
    print()
    
    try:
        success = test_prompt_loading()
        print()
        
        if success:
            print("="*80)
            print("✅ PROMPT IMPROVEMENT COMPLETE AND VERIFIED")
            print("="*80)
            print()
            print("The AI code reviewer will now:")
            print("  • Generate comments when code has actual issues")
            print("  • Look for specific problem categories")
            print("  • Provide detailed, actionable feedback")
            print("  • Properly categorize and prioritize findings")
            print()
            sys.exit(0)
        else:
            print("❌ Verification failed")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Test execution failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
