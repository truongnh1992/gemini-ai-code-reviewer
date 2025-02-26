# OpenAI Code Reviewer

A GitHub Action that automatically reviews pull requests using OpenAI's GPT-3.5 Turbo.

## Features

- Review your PRs using OpenAI API
- Give use comments and suggestions to improve the source codes

![Demo](./Demo.png)

## Setup

1. To use this GitHub Action, you need an OpenAI API key. If you don't have one, sign up for an API key
   at [OpenAI Platform](https://platform.openai.com/).

2. Add the OpenAI API key as a GitHub Secret in your repository with the name `OPENAI_API_KEY`. You can find more
   information about GitHub Secrets [here](https://docs.github.com/en/actions/reference/encrypted-secrets).

3. Create a `.github/workflows/code-review.yml` file in your repository and add the following content:

```yaml
name: OpenAI Code Reviewer

on:
  issue_comment:
    types: [created]

permissions: write-all

jobs:
  openai-code-review:
    runs-on: ubuntu-latest
    if: |
      github.event.issue.pull_request &&
      contains(github.event.comment.body, '/openai-review')
    steps:
      - name: PR Info
        run: |
          echo "Comment: ${{ github.event.comment.body }}"
          echo "Issue Number: ${{ github.event.issue.number }}"
          echo "Repository: ${{ github.repository }}"

      - name: Checkout Repo
        uses: actions/checkout@v3
        with:
          fetch-depth: 0

      - name: Get PR Details
        id: pr
        run: |
          PR_JSON=$(gh api repos/${{ github.repository }}/pulls/${{ github.event.issue.number }})
          echo "head_sha=$(echo $PR_JSON | jq -r .head.sha)" >> $GITHUB_OUTPUT
          echo "base_sha=$(echo $PR_JSON | jq -r .base.sha)" >> $GITHUB_OUTPUT
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - uses: Tomas-Jankauskas/ai-code-reviewer@main
        with:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          OPENAI_MODEL: gpt-3.5-turbo # Optional, default is `gpt-3.5-turbo`
          EXCLUDE: "*.md,*.txt,package-lock.json,*.yml,*.yaml"
```
> If you don't set `OPENAI_MODEL`, the default model is `gpt-3.5-turbo`. You can also use other OpenAI models like `gpt-4` if you have access to them.

4. Commit codes to your repository, and working on your pull requests.
5. When you're ready to review the PR, you can trigger the workflow by commenting `/openai-review` in the PR.

## Alternative Workflow Files

This repository includes two ready-to-use workflow files that you can download and add to your project:

1. **General Code Review Workflow**: [openai-code-review-workflow.yml](https://github.com/Tomas-Jankauskas/ai-code-reviewer/blob/main/openai-code-review-workflow.yml)
   - Triggered by commenting `/openai-review` on a PR
   - Reviews all code changes except common non-code files

2. **Vue Component Review Workflow**: [vue-code-review-workflow.yml](https://github.com/Tomas-Jankauskas/ai-code-reviewer/blob/feature/improved-todo-component/vue-code-review-workflow.yml)
   - Triggered by commenting `/openai-review-vue` on a PR
   - Specifically focuses on Vue component files
   - Ignores non-code files like markdown, JSON, YAML, etc.

To use these workflows:
1. Download the desired workflow file
2. Create a `.github/workflows` directory in your repository
3. Place the workflow file in the `.github/workflows` directory
4. Add your OpenAI API key as a repository secret named `OPENAI_API_KEY`

## How It Works

This GitHub Action uses the OpenAI API to provide code review feedback. It works by:

1. **Analyzing the changes**: It grabs the code modifications from your pull request and filters out any files you don't want reviewed.
2. **Consulting the OpenAI model**: It sends chunks of the modified code to OpenAI for analysis.
3. **Providing feedback**: OpenAI examines the code and generates review comments.
4. **Delivering the review**: The Action adds the comments directly to your pull request on GitHub.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more information.