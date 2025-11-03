# save_linear_auth.py
# A new, more reliable script to manually save our Linear auth state.
# We are NOT using codegen anymore.

from playwright.sync_api import sync_playwright
import time

AUTH_FILE_PATH = "linear_auth.json"

# !!! --- IMPORTANT --- !!!
# Paste your *actual* workspace URL here.
# For example: "https://linear.app/jiayang-li/team/JIA/active"
YOUR_WORKSPACE_URL_HERE = "https://linear.app/jiayang-li/team/JIA/active"
# !!! ----------------- !!!


def save_auth_state_manually():
    if YOUR_WORKSPACE_URL_HERE == "https://[REPLACE-THIS-WITH-YOUR-URL].linear.app":
         print("="*50)
         print("ERROR: Please open 'save_linear_auth.py' and edit the")
         print("'YOUR_WORKSPACE_URL_HERE' variable with your real Linear URL.")
         print("="*50)
         return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        # Go directly to your workspace login page
        print(f"Navigating to: {YOUR_WORKSPACE_URL_HERE}")
        page.goto(YOUR_WORKSPACE_URL_HERE)
        
        # --- USER ACTION REQUIRED ---
        print("\n" + "="*50)
        print(">>> A BROWSER WINDOW IS OPEN <<<")
        print("1. Please log in to Linear using the 'Continue with email' method.")
        print("2. Enter your email, get the code, and submit it.")
        print("3. Wait until you can see your FULL dashboard.")
        print("\n   >>> AFTER YOU ARE LOGGED IN <<<   ")
        print("4. Come back to this terminal and press the 'Enter' key.")
        print("="*50 + "\n")
        
        # This line pauses the script and waits for you to press Enter
        input("Press Enter when you are logged in and see your dashboard...")
        
        # Now that you're logged in, we save the state
        print("Saving authentication state...")
        
        # This is the magic line. We save the state from the *context*
        storage_state = context.storage_state()
        
        with open(AUTH_FILE_PATH, 'w') as f:
            import json
            json.dump(storage_state, f, indent=4)
            
        print(f"Authentication state saved to {AUTH_FILE_PATH}")
        print("You can now run 'test_auth.py' to verify.")
        
        time.sleep(2)
        browser.close()

if __name__ == "__main__":
    save_auth_state_manually()