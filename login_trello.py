# login_trello.py
# A separate script to perform manual login for Trello
# and save the session state for our agent.

import time
from playwright.sync_api import sync_playwright

# Define the path for our new Trello auth file
TRELLO_AUTH_FILE = "trello_auth.json"

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://trello.com/login")

        print("\n" + "="*50)
        print("  Please log in to Trello manually in the browser.")
        print("  After successful login, this script will save")
        print("  the session state.")
        print("  We will wait for 60 seconds.")
        print("="*50)

        # Provide 60 seconds for manual login
        page.wait_for_timeout(60000)

        # After login, save the storage state
        context.storage_state(path=TRELLO_AUTH_FILE)
        print(f"Successfully saved Trello auth state to: {TRELLO_AUTH_FILE}")
        
        browser.close()

if __name__ == "__main__":
    main()