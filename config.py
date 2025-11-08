# config.py
"""
网站配置模块
包含所有支持网站的配置信息和配置检测逻辑
"""

# --- Configuration ---
# This dictionary maps domain keywords to their specific settings.
# This is the core of our generalization strategy.
SITE_CONFIGS = {
    "trello": {
        "auth_file": "trello_auth.json",
        "anchor_selector": '[data-testid="head-container"]',
        "default_goal": (
            "Find the list named 'To Do'. Click the 'Add a card' button. "
            "Type 'My First AI Trello Card' and click 'Add card'."
        ),
        "site_context_prompt": (
            "We are on Trello. The primary items are called 'Cards' and 'Lists'."
        )
    },
    "linear": {
        "auth_file": "linear_auth.json",
        "anchor_selector": 'text="Inbox"',
        "default_goal": (
            "Find the button to create a new issue and click it. "
            "Then, type 'My First AI Issue' into the title field."
        ),
        "site_context_prompt": (
            "We are on Linear. The primary items are called 'Issues' and 'Projects'."
        )
    },
    "notion": {
        "auth_file": "notion_auth.json",
        "anchor_selector": 'text="Home"', # Waits for the sidebar to load
        "default_goal": (
            "Execute the following commands step by step."
            "Find the 'Add New' button on the side bar and click it. And don't touch it again. "
            "After that, in the new modal, click 'Projects' button. After that, click 'Continue' button."
            "After that, click 'Done' button and don't click 'Add New' again. "
            "End the loop as soon as you finish all these steps, do not repeat any steps"
        ),
        "site_context_prompt": (
            "We are on Notion. The primary items are called 'Pages' and 'Databases'. "
            "The main content area is often editable."
        )
    }
    # We can add more sites here (e.g., "github", "jira")
}


def get_site_config(url: str) -> dict:
    """
    Detects the site based on the URL and returns the
    corresponding configuration dictionary.
    """
    if "trello.com" in url:
        print("Site detected: Trello")
        return SITE_CONFIGS["trello"]
    elif "linear.app" in url:
        print("Site detected: Linear")
        return SITE_CONFIGS["linear"]
    elif "notion.so" in url:
        print("Site detected: Notion")
        return SITE_CONFIGS["notion"]
    
    # Fallback or error
    print(f"Warning: No specific config found for URL: {url}")
    print("Falling back to default behavior. This may fail.")
    # We return a basic structure to avoid crashing, 
    # but auth will likely fail.
    return {
        "auth_file": "default_auth.json",
        "anchor_selector": "body", # A generic selector
        "default_goal": "No default goal specified.",
        "site_context_prompt": "We are on an unknown website."
    }
