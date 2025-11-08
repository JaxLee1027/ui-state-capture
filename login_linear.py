# login_linear.py
# A separate script to perform manual login for Linear
# and save the session state for our agent.
# This version waits for the user to press ENTER, which is reliable.

import time
from playwright.sync_api import sync_playwright

# Define the path for our new Linear auth file
LINEAR_AUTH_FILE = "linear_auth.json"

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # Go to the Linear login page
        page.goto("https://linear.app/login")

        print("\n" + "="*50)
        print("  Please log in to Linear manually in the browser.")
        print("  (This may involve Google, email, etc.)")
        print("\n  After login, please navigate to the exact workspace")
        print("  or team page our agent should work on.")
        print("\n  *** WHEN YOU ARE ON THE CORRECT LINEAR PAGE ***")
        print("  *** COME BACK HERE AND PRESS 'ENTER' TO SAVE ***")
        print("="*50)
        
        # Wait for user input (Enter key) instead of a timer
        input() 
        
        # After user presses Enter, save the storage state
        context.storage_state(path=LINEAR_AUTH_FILE)
        print(f"Successfully saved Linear auth state to: {LINEAR_AUTH_FILE}")
        
        browser.close()

if __name__ == "__main__":
    main()