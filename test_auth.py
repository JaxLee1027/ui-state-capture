# test_auth.py
# This script tests if our saved auth file works.

from playwright.sync_api import sync_playwright
import os

AUTH_FILE_PATH = "linear_auth.json" 
# The workspace url
WORKSPACE_URL = "https://linear.app/jiayang-li/team/JIA/active"


# A unique element on the dashboard
ANCHOR_SELECTOR = 'text="All issues"' 


def test_saved_auth():
    if not os.path.exists(AUTH_FILE_PATH):
        print(f"Error: Auth file '{AUTH_FILE_PATH}' not found.")
        print("Please run 'save_linear_auth.py' first to generate it.")
        return

    if WORKSPACE_URL == "https://[REPLACE-THIS-WITH-YOUR-URL].linear.app":
         print("="*50)
         print("ERROR: Please open 'test_auth.py' and edit the")
         print("'WORKSPACE_URL' variable with your real Linear URL.")
         print("="*50)
         return

    # --- NEW ERROR CHECK ---
    if ANCHOR_SELECTOR == 'text="All issues"' and not os.path.exists(AUTH_FILE_PATH): # Only if it's default and auth not present
         print("="*50)
         print("WARNING: Please open 'test_auth.py' and verify/edit the")
         print("'ANCHOR_SELECTOR' variable with a real selector.")
         print("="*50)
    # --- END NEW ERROR CHECK ---

    with sync_playwright() as p:
        print("Launching browser...")
        browser = p.chromium.launch(headless=False, slow_mo=500)

        print(f"Loading saved auth state from {AUTH_FILE_PATH}...")
        context = browser.new_context(storage_state=AUTH_FILE_PATH)

        page = context.new_page()

        print(f"Navigating directly to your workspace: {WORKSPACE_URL}")
        page.goto(WORKSPACE_URL)

        print(f"Waiting for dashboard element to appear: {ANCHOR_SELECTOR}...")
        # Use 'state="visible"' to ensure it's not just in the DOM, but actually visible
        page.wait_for_selector(ANCHOR_SELECTOR, state="visible", timeout=30000) # 30-second timeout
        print("Dashboard element found!")

        screenshot_path = "linear_dashboard.png"
        page.screenshot(path=screenshot_path)

        print(f"Screenshot saved to {screenshot_path}")
        print("Check 'linear_dashboard.png' to see if you are logged in and dashboard is fully loaded.")

        page.wait_for_timeout(3000)
        browser.close()
        print("Test complete.")

if __name__ == "__main__":
    test_saved_auth()