# main.py

from playwright.sync_api import sync_playwright

def run_test():
    # Use a 'with' statement to properly manage resources
    with sync_playwright() as p:

        # Launch a browser. We use Chromium here.
        # headless=False means we will actually see the browser window open.
        # This is great for debugging and seeing what the agent is doing.
        browser = p.chromium.launch(headless=False, slow_mo=500)

        # Create a new page (like a new tab)
        page = browser.new_page()

        # Go to a simple website
        print("Navigating to https://www.google.com ...")
        page.goto("https://www.google.com")

        # Take a screenshot and save it as 'google_test.png'
        page.screenshot(path="google_test.png")
        print("Screenshot 'google_test.png' saved!")

        # Close the browser
        browser.close()
        print("Browser closed.")

# This is the standard entry point for a Python script
if __name__ == "__main__":
    run_test()