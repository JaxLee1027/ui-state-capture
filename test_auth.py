# test_auth.py
# This script tests if our saved auth file works.

from playwright.sync_api import sync_playwright
import os

AUTH_FILE_PATH = "linear_auth.json" # Keep this as 'linear.json'
# !!! --- IMPORTANT --- !!!
# Replace this with your *actual* workspace URL,
# for example: "https://softlight-demo.linear.app"
YOUR_WORKSPACE_URL_HERE = "https://linear.app/jiayang-li/team/JIA/active"
# !!! ----------------- !!!

# !!! --- NEW --- !!!
# Replace this with a selector for a unique element on your dashboard.
# Examples: '[data-testid="Inbox"]', 'text="Projects"', 'button:has-text("Add a new issue")'
YOUR_ANCHOR_SELECTOR_HERE = 'text="All issues"' # <-- Adjust this based on your finding!
# !!! --------- !!!

def test_saved_auth():
    if not os.path.exists(AUTH_FILE_PATH):
        print(f"Error: Auth file '{AUTH_FILE_PATH}' not found.")
        print("Please run 'save_linear_auth.py' first to generate it.")
        return

    if YOUR_WORKSPACE_URL_HERE == "https://[REPLACE-THIS-WITH-YOUR-URL].linear.app":
         print("="*50)
         print("ERROR: Please open 'test_auth.py' and edit the")
         print("'YOUR_WORKSPACE_URL_HERE' variable with your real Linear URL.")
         print("="*50)
         return

    # --- NEW ERROR CHECK ---
    if YOUR_ANCHOR_SELECTOR_HERE == '[data-testid="Inbox"]' and not os.path.exists(AUTH_FILE_PATH): # Only if it's default and auth not present
         print("="*50)
         print("WARNING: Please open 'test_auth.py' and verify/edit the")
         print("'YOUR_ANCHOR_SELECTOR_HERE' variable with a real selector.")
         print("="*50)
    # --- END NEW ERROR CHECK ---

    with sync_playwright() as p:
        print("Launching browser...")
        browser = p.chromium.launch(headless=False, slow_mo=500)

        print(f"Loading saved auth state from {AUTH_FILE_PATH}...")
        context = browser.new_context(storage_state=AUTH_FILE_PATH)

        page = context.new_page()

        print(f"Navigating directly to your workspace: {YOUR_WORKSPACE_URL_HERE}")
        page.goto(YOUR_WORKSPACE_URL_HERE)

        # !!! --- NEW CRITICAL WAIT STEP --- !!!
        print(f"Waiting for dashboard element to appear: {YOUR_ANCHOR_SELECTOR_HERE}...")
        # Use 'state="visible"' to ensure it's not just in the DOM, but actually visible
        page.wait_for_selector(YOUR_ANCHOR_SELECTOR_HERE, state="visible", timeout=30000) # 30-second timeout
        print("Dashboard element found!")
        # !!! -------------------------- !!!

        screenshot_path = "linear_dashboard.png"
        page.screenshot(path=screenshot_path)

        print(f"Screenshot saved to {screenshot_path}")
        print("Check 'linear_dashboard.png' to see if you are logged in and dashboard is fully loaded.")

        page.wait_for_timeout(3000)
        browser.close()
        print("Test complete.")

if __name__ == "__main__":
    test_saved_auth()