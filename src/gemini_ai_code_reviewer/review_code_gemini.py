import os

import _review_code_gemini_github
import _review_code_gemini_gitlab

PLATFORM_HANDLERS = {
    "github": _review_code_gemini_github.main,
    "gitlab": _review_code_gemini_gitlab.main,
}


def main():
    """Main function to execute the code review process."""
    platform = os.environ.get("GIT_PLATFORM", "local")
    print(f"Platform: {platform}")

    handler = PLATFORM_HANDLERS.get(platform)
    if handler:
        handler()
    else:
        print(f"Unsupported platform: {platform}")

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Error: {error}")
        import traceback
        traceback.print_exc()
        exit(1)
