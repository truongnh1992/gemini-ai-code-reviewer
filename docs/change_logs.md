# Change Logs

## Version 2.0.0 (2025-03-03)

### Major Changes
- Added support for multiple AI providers through a modular architecture
  - Introduced abstract `AIProvider` interface
  - Added support for Deepseek AI alongside Gemini
  - Implemented provider factory pattern for easy provider management

### Features
- New AI Provider System:
  - Abstract `AIProvider` interface with standardized methods:
    - `configure()`: Set up provider credentials and settings
    - `generate_review()`: Generate code review from prompt
    - `get_name()`: Get provider identifier
  - GeminiProvider implementation:
    - Uses Google's Gemini API
    - Configurable model selection via GEMINI_MODEL
    - Maintained backward compatibility
  - DeepseekProvider implementation:
    - Integration with Deepseek's code review capabilities
    - Configurable via DEEPSEEK_API_KEY and DEEPSEEK_MODEL

### Configuration Changes
- New environment variables:
  - `AI_PROVIDER`: Select AI provider ('gemini' or 'deepseek')
  - `DEEPSEEK_API_KEY`: API key for Deepseek provider
  - `DEEPSEEK_MODEL`: Model selection for Deepseek (default: 'deepseek-coder-33b-instruct')

### Action.yml Updates
- Added new input parameters:
  - `AI_PROVIDER`: Choose between available AI providers
  - `DEEPSEEK_API_KEY`: Configure Deepseek authentication
  - `DEEPSEEK_MODEL`: Specify Deepseek model
- Maintained existing Gemini configurations
- Updated description to reflect multi-provider support

### Code Structure Improvements
- Integrated provider system directly in review_code_gemini.py
- Improved error handling for provider configuration
- Better logging of provider-specific operations
- Cleaner code organization with class-based provider implementations

### Usage Instructions
1. Default Provider (Gemini):
   ```yaml
   - uses: truongnh1992/ai-code-reviewer@v2
     with:
       GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
       GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
   ```

2. Using Deepseek Provider:
   ```yaml
   - uses: truongnh1992/ai-code-reviewer@v2
     with:
       GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
       AI_PROVIDER: 'deepseek'
       DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
   ```

### Future Extensibility
- Easy addition of new AI providers by implementing the `AIProvider` interface
- Standardized way to add provider-specific configurations
- Simplified maintenance and updates for individual providers