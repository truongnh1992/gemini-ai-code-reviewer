# Testing the OpenAI Code Reviewer with Vue Components

This document provides instructions for testing the OpenAI Code Reviewer with Vue.js components.

## Test Vue Component

I've created a sample Vue component (`src/components/TodoList.vue`) with several intentional issues that the code reviewer should identify:

1. Unused variable (`unusedVar`) in the data object
2. Using `:key="index"` in v-for loops (not recommended for performance reasons)
3. Potential security issue with localStorage (using JSON.parse without validation)
4. Performance issue with watching the entire todos array with deep watching
5. No error handling for localStorage operations

## How to Test

### Local Testing

To test the code reviewer locally with the Vue component:

1. Set your OpenAI API key as an environment variable:
   ```bash
   export OPENAI_API_KEY=your-api-key-here
   ```

2. Run the Vue component test script:
   ```bash
   python test_vue_review.py
   ```

3. Review the output to see what issues the OpenAI model identifies in the Vue component.

### Testing in a GitHub Workflow

To test the code reviewer in a real GitHub workflow:

1. Fork this repository
2. Add your OpenAI API key as a repository secret named `OPENAI_API_KEY`
3. Create a new branch and make changes to the Vue component
4. Create a pull request
5. Comment `/openai-review` on the pull request
6. The OpenAI code reviewer will analyze your changes and provide feedback

## Expected Results

The code reviewer should identify most or all of the intentional issues in the Vue component, such as:

- The unused variable in the data object
- The potential security issue with localStorage
- The performance issue with watching the entire todos array
- Using index as a key in v-for loops

The exact feedback will depend on the OpenAI model's analysis, but it should provide helpful suggestions for improving the code.

## Customizing the Test

You can modify the Vue component to include different issues or patterns that you want to test with the code reviewer. The test script simulates a pull request diff, so you can also modify it to test different scenarios.