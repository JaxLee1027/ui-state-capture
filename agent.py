# agent.py
"""
主程序入口
协调各个模块完成网页自动化任务
"""

import os
import argparse
from playwright.sync_api import sync_playwright

# Import our modularized components
from config import get_site_config
from dom_processor import get_simplified_dom
from ai_agent import think
from web_actions import act

# Dataset directory setup
DATASET_DIR = "dataset"
os.makedirs(DATASET_DIR, exist_ok=True)


def run_agent_loop(
    goal: str,
    task_name: str,
    workspace_url: str,
    anchor_selector: str, 
    config: dict
):
    """
    Outer loop that coordinates Observe -> Think -> Act steps.
    It now uses a dynamic config object to load the correct auth file and provide site context to the think phase.
    """

    auth_file = config["auth_file"]
    if not os.path.exists(auth_file):
        print(
            # Use the dynamic auth_file variable in the error
            f"Error: auth file '{auth_file}' not found. "
            f"Please run the login script for this site first."
        )
        return

    if not workspace_url or "[REPLACE-THIS]" in workspace_url:
        print("ERROR: a valid --url argument must be provided.")
        return

    task_dir = os.path.join(DATASET_DIR, task_name)
    os.makedirs(task_dir, exist_ok=True)
    print(
        f"Starting task: '{goal}'. Screenshots will be stored in: {task_dir}"
    )

    with sync_playwright() as p:
        # slow_mo adds a small delay to each action, which helps with debugging
        browser = p.chromium.launch(headless=False, slow_mo=250)
        context = browser.new_context(storage_state=auth_file)
        page = context.new_page()

        print(f"Navigating to workspace: {workspace_url}")
        page.goto(workspace_url)
        print("Taking screenshot *immediately* after navigation...")
        page.screenshot(
            path=os.path.join(task_dir, "debug_01_post_navigation.png")
        )
        try:
            print(
                f"Waiting for dashboard to load (waiting for selector: {anchor_selector})..."
            )
            page.wait_for_selector(anchor_selector, state="visible", timeout=10000)
            print("Dashboard loaded. Starting agent loop.")

            action_history = []
            step = 1
            max_steps = 10

            while True:
                print(f"\\n--- Step {step} ---")

                # Allow the UI to settle before observing
                print("Waiting for UI to settle...")
                page.wait_for_timeout(3000)

                # 1. Observe
                simplified_dom = get_simplified_dom(page)
                if not simplified_dom:
                    print("Simplified DOM is empty. Stopping agent.")
                    break

                # 2. Think
                site_context = config["site_context_prompt"]
                action = think(goal, simplified_dom, action_history, site_context)

                # 3. Act
                continue_loop = act(page, action, task_dir, step)

                # 4. Update history for introspection in the next step
                if action.get("action") == "type":
                    action_history.append(
                        f"Step {step}: Typed '{action.get('text')}' into {action.get('id')}"
                    )
                elif action.get("action") == "click":
                    action_history.append(
                        f"Step {step}: Clicked {action.get('id')}"
                    )

                if not continue_loop or step >= max_steps:
                    if step >= max_steps:
                        print(
                            f"Reached step limit ({max_steps}). Stopping agent."
                        )
                    break

                step += 1

            print("\\nAgent loop finished.")

        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            print("Dumping the page HTML to debug_page_content.html ...")
            try:
                html_content = page.content()
                debug_html_path = os.path.join(task_dir, "debug_page_content.html")
                with open(debug_html_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
                print(f"HTML dump saved to: {debug_html_path}")
            except Exception as e_html:
                print(f"Could not dump HTML: {e_html}")
            print("Running get_simplified_dom() at point of failure...")
            try:
                # We call the function manually
                simplified_dom_at_failure = get_simplified_dom(page)
                debug_dom_path = os.path.join(task_dir, "debug_simplified_dom.txt")
                
                with open(debug_dom_path, "w", encoding="utf-8") as f:
                    f.write(simplified_dom_at_failure)
                    
                print(f"Simplified DOM saved to: {debug_dom_path}")
                
                # # Also print it to the console if it's not too long
                # print("\\n--- Simplified DOM at Failure ---")
                # if simplified_dom_at_failure:
                #     print(simplified_dom_at_failure)
                # else:
                #     print("[Simplified DOM was empty]")
                # print("----------------------------------\\n")
                
            except Exception as e_dom:
                print(f"Could not get simplified DOM: {e_dom}")
            print("Capturing a screenshot of the critical error state...")
            page.screenshot(path=os.path.join(task_dir, "critical_error.png"))

        print("Pausing for 5 seconds before closing the browser.")
        page.wait_for_timeout(5000)
        browser.close()


if __name__ == "__main__":
    """
    Entry point.
    Parses command-line arguments and starts the agent loop.
    loads the correct config, and starts the agent loop.
    """

    parser = argparse.ArgumentParser(
        description="Run the AI agent on a Linear web task."
    )

    parser.add_argument(
        "--url",
        type=str,
        required=True,
        help="Specific workspace URL (e.g., Trello, Linear) where the agent starts.",
    )

    parser.add_argument(
        "--selector",
        type=str,
        default=None, # Default is None, will be loaded from config
        help="(Optional) Override the site's default anchor selector.",
    )

    parser.add_argument(
        "--goal",
        type=str,
        default=None, # [MODIFIED] Default is None, will be loaded from config
        help="(Optional) Override the site's default high-level task goal.",
    )

    parser.add_argument(
        "--task-name",
        type=str,
        default="agent_task_run_1", # [MODIFIED] A more generic default name
        help="Folder name inside ./dataset/ for storing screenshots.",
    )

    args = parser.parse_args()

    # 1. Detect config from the *required* URL
    config = get_site_config(args.url)
    if not config:
        print(f"Error: Could not determine configuration for URL {args.url}")
        raise SystemExit(1)

    # 2. Use config defaults if user did not provide overrides
    
    # If user did not provide --goal, use the site's default goal
    if args.goal is None:
        args.goal = config["default_goal"]
        print(f"No --goal provided. Using default for this site:")
        print(f'"{args.goal}"')
    else:
        print(f"Using user-provided --goal:")
        print(f'"{args.goal}"')

    # If user did not provide --selector, use the site's default selector
    if args.selector is None:
        args.selector = config["anchor_selector"]
        print(f"No --selector provided. Using default for this site:")
        print(f'"{args.selector}"')
    else:
        print(f"Using user-provided --selector:")
        print(f'"{args.selector}"')
    
    # --- End of New Logic ---

    # Pass the entire config object and the resolved anchor_selector
    run_agent_loop(
        goal=args.goal,
        task_name=args.task_name,
        workspace_url=args.url,
        anchor_selector=args.selector, 
        config=config 
    )
