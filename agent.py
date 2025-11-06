# agent.py
# Final consolidated agent script for Linear issue creation

import os
import time
import json
import argparse
from playwright.sync_api import sync_playwright, Page
from openai import OpenAI

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

# Function to detect and retrieve site-specific config
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

DATASET_DIR = "dataset"
os.makedirs(DATASET_DIR, exist_ok=True)
# ---------------------


# Initialize the OpenAI client
try:
    # OpenAI client uses the environment variable OPENAI_API_KEY
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
except KeyError:
    print("ERROR: OPENAI_API_KEY environment variable is not set.")
    print("Environment example on Windows:  set OPENAI_API_KEY=sk-...")
    raise SystemExit(1)


def get_simplified_dom(page: Page) -> str:
    """
    (Observe)
    This version adds a check for [role="menu"].
    Our new focus hierarchy is:
    1. Try to find a [role="dialog"] (main modal).
    2. If no dialog, *then* try to find a [role="menu"] (popover menu).
    3. If neither, use the whole document.
    This prevents the agent from clicking the '...' button *through* the
    menu it just opened.
    """

    js_script = """
    () => {
        let agentId = 1;
        let simplifiedDom = [];

        // 1. Cleanup: Remove all old tags first
        document.querySelectorAll('[data-agent-id]').forEach(el => {
            el.removeAttribute('data-agent-id');
        });
        
        // --- [THE FIX IS HERE] ---
        let searchContext = document; // Default to the whole page

        // 1. Check for Modals (Priority 1)
        const allDialogs = document.querySelectorAll('[role="dialog"][aria-modal="true"]');
        let mainModal = null;
        if (allDialogs.length > 0) {
            for (const dialog of allDialogs) {
                if (
                    dialog.querySelector('input, textarea, [contenteditable="true"], [role="textbox"]')
                ) {
                    mainModal = dialog;
                    break;
                }
            }
            if (mainModal) {
                searchContext = mainModal;
            } else {
                searchContext = allDialogs[0];
            }
        } 
        // 2. Check for Menus (Priority 2)
        else { 
            // Only check for menus if no dialog is open
            // This is for the '...' issue options menu
            const allMenus = document.querySelectorAll('[role="menu"]');
            if (allMenus.length > 0) {
                // Use the first active menu found
                searchContext = allMenus[0]; 
            }
        }
        // --- [END OF FIX] ---
        

        // 3. Tagging: Find elements *within the smart searchContext*
        const elements = searchContext.querySelectorAll(
            'a, button, input, textarea, [role="button"], [role="link"], ' +
            '[role="tab"], [role="option"], [role="menuitem"], ' +
            '[contenteditable="true"], [role="textbox"]'
        );

        for (const el of elements) {
            // ... (rest of the function is identical to our last version) ...
            if (!el) continue;

            const style = window.getComputedStyle(el);
            if (
                el.disabled ||
                style.visibility === 'hidden' ||
                style.display === 'none' ||
                el.offsetWidth === 0 ||
                el.offsetHeight === 0
            ) {
                continue;
            }

            const tagName = el.tagName.toLowerCase();
            const inputType = (tagName === 'input') ? el.getAttribute('type') : null;
            const isContentEditable =
                el.getAttribute('contenteditable') === 'true' ||
                el.getAttribute('role') === 'textbox';

            let text =
                (el.innerText ||
                 el.getAttribute('aria-label') ||
                 el.getAttribute('placeholder') ||
                 el.getAttribute('data-placeholder') ||
                 '').
                trim();

            if (tagName === 'input' && inputType === 'checkbox' && !text && el.id) {
                const label = document.querySelector('label[for="' + el.id + '"]');
                if (label) {
                    text = (label.innerText || '').trim();
                }
            }
            if (tagName === 'input' && inputType === 'checkbox' && !text && el.parentElement) {
                text = (el.parentElement.innerText || '').trim();
            }

            text = text.replace(/\\s+/g, ' ').substring(0, 100);

            const isCheckbox = (tagName === 'input' && inputType === 'checkbox');
            let isTextInput = false;
            if (tagName === 'textarea') {
                isTextInput = true;
            } else if (tagName === 'input' && !isCheckbox && inputType !== 'radio') {
                isTextInput = true;
            } else if (isContentEditable) {
                isTextInput = true;
            }
            
            const uniqueId = 'agent-id-' + (agentId++).toString();
            el.setAttribute('data-agent-id', uniqueId);

            simplifiedDom.push({
                tag: tagName,
                id: uniqueId,
                text: text,
                inputType: inputType,
                isTextInput: isTextInput,
                isCheckbox: isCheckbox
            });
        }
        
        // 6. Formatting: Return a clean list for the LLM
        return simplifiedDom.map(el => {
            if (el.isTextInput) {
                const label = el.text || '';
                return '<TEXT-INPUT data-agent-id="' + el.id +
                       '" label="' + label + '"></TEXT-INPUT>';
            } else if (el.isCheckbox) {
                const label = el.text || '';
                return '<CHECKBOX data-agent-id="' + el.id +
                       '" label="' + label + '"></CHECKBOX>';
            } else {
                const label = el.text || '';
                return '<' + el.tag.toUpperCase() +
                       ' data-agent-id="' + el.id + '">' +
                       label +
                       '</' + el.tag.toUpperCase() + '>';
            }
        }).join('\\n');
    }
    """

    try:
        simplified_dom_string = page.evaluate(js_script)
        return simplified_dom_string
    except Exception as e:
        print(f"Error injecting JS to simplify DOM: {e}")
        return ""


def think(goal: str, dom: str, history: list, site_context: str) -> dict:
    """
    Think phase.
    Sends the current goal, DOM, and action history to the LLM
    and receives a structured action description in JSON form.
    """

    history_string = "\n".join(history)

    prompt = f"""
    We are an AI agent.
    [SITE CONTEXT]
    {site_context}

    Our high-level, multi-step goal is: "{goal}"

    This is our HISTORY of actions taken so far:
    ---
    {history_string}
    ---

    This is the CURRENT simplified DOM (what is visible right now):
    ---
    {dom}
    ---

    INSTRUCTIONS:
    1. Analyze our goal.
    2. Analyze our HISTORY to understand the current state.
    3. Analyze the current DOM.
    4. Decide the single next logical step.

    CRITICAL RULES:
    - We are an AI agent. Our GOAL is a multi-step plan.
    - Our HISTORY shows what we *just completed*.
    - Our DOM is what is visible *right now*.

    - **[PRIORITY 1: HISTORY]** ALWAYS check the HISTORY first.
    - If the GOAL is "Step 1: A, Step 2: B" and HISTORY shows "Clicked A",
      our *only job* is to find "B" in the current DOM.
    - NEVER repeat a step from the GOAL that is already in the HISTORY,
      even if the element (like "A") is still visible.
    - Prioritize the *next uncompleted step* of the GOAL.

    - **[PRIORITY 2: ACTIONS]**
    - Editable text fields appear as <TEXT-INPUT ...>.
    - If the goal is to type into a <TEXT-INPUT>, the ONLY action MUST be "type".
    - NEVER, under any circumstances, issue a "click" action on a <TEXT-INPUT> element.
    - The "type" action is only for <TEXT-INPUT>. Never "type" on a <BUTTON> or <CHECKBOX>.

    - **[PRIORITY 3: FAILURE]**
    - "fail" is a last resort. If the DOM is empty or no elements match the
      *next* step of the GOAL, wait and observe again. Only fail if
      progress is impossible.

    Valid actions (respond only with JSON, no extra text):

    1. Click:
    {{"action": "click", "id": "agent-id-..."}}

    2. Type:
    {{"action": "type", "id": "agent-id-...", "text": "text to type..."}}

    3. Finish:
    {{"action": "finish", "reason": "why the goal is considered complete"}}

    4. Fail:
    {{"action": "fail", "reason": "why progress is blocked"}}
    """

    print("Agent is thinking...")
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )

        response_text = response.choices[0].message.content

        # Allow fenced JSON blocks and plain JSON
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]

        action = json.loads(response_text)
        print(f"Agent decided to: {action}")
        return action

    except Exception as e:
        print(f"Error during think phase (LLM call or JSON parsing): {e}")
        return {"action": "fail", "reason": f"LLM or JSON parsing error: {e}"}


def act(page: Page, action: dict, task_dir: str, step: int) -> bool:
    """
    Act phase.
    Executes the chosen action inside the browser and captures
    before/after screenshots.

    Returns:
        True  -> continue the loop
        False -> stop the loop
    """

    before_screenshot_path = os.path.join(task_dir, f"step_{step:02d}_before.png")
    page.screenshot(path=before_screenshot_path)

    action_type = action.get("action")

    try:
        if action_type == "click":
            element_id = action.get("id")
            selector = f'[data-agent-id="{element_id}"]'
            print(f"Executing: click on element {element_id}")
            page.locator(selector).click()

        elif action_type == "type":
            element_id = action.get("id")
            text_to_type = action.get("text")
            selector = f'[data-agent-id="{element_id}"]'
            locator = page.locator(selector)

            # Safety check: avoid typing into checkbox elements
            tag = locator.evaluate("el => el.tagName.toLowerCase()")
            input_type = locator.evaluate("el => el.getAttribute('type')")

            if tag == "input" and input_type == "checkbox":
                print(f"Refusing to type into checkbox element {element_id}")
                page.screenshot(
                    path=os.path.join(task_dir, f"step_{step:02d}_type_checkbox_error.png")
                )
                return False

            print(f"Executing: type '{text_to_type}' into element {element_id}")
            locator.fill(text_to_type)

        elif action_type == "finish":
            print(f"Task finished. Reason: {action.get('reason')}")
            return False

        elif action_type == "fail":
            print(f"Task failed. Reason: {action.get('reason')}")
            return False

        else:
            print(f"Unknown action type: {action_type}")
            return False

    except Exception as e:
        print(f"Error during act phase: {e}")
        page.screenshot(
            path=os.path.join(task_dir, f"step_{step:02d}_action_error.png")
        )
        return False

    # Allow UI animations to settle after the action
    page.wait_for_timeout(2000)

    after_screenshot_path = os.path.join(task_dir, f"step_{step:02d}_after.png")
    page.screenshot(path=after_screenshot_path)

    return True


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
            page.wait_for_selector(anchor_selector, state="visible", timeout=30000)
            print("Dashboard loaded. Starting agent loop.")

            action_history = []
            step = 1
            max_steps = 10

            while True:
                print(f"\n--- Step {step} ---")

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

            print("\nAgent loop finished.")

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
                # print("\n--- Simplified DOM at Failure ---")
                # if simplified_dom_at_failure:
                #     print(simplified_dom_at_failure)
                # else:
                #     print("[Simplified DOM was empty]")
                # print("----------------------------------\n")
                
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
        print(f"\"{args.goal}\"")
    else:
        print(f"Using user-provided --goal:")
        print(f"\"{args.goal}\"")

    # If user did not provide --selector, use the site's default selector
    if args.selector is None:
        args.selector = config["anchor_selector"]
        print(f"No --selector provided. Using default for this site:")
        print(f"\"{args.selector}\"")
    else:
        print(f"Using user-provided --selector:")
        print(f"\"{args.selector}\"")
    
    # --- End of New Logic ---

    # Pass the entire config object and the resolved anchor_selector
    run_agent_loop(
        goal=args.goal,
        task_name=args.task_name,
        workspace_url=args.url,
        anchor_selector=args.selector, 
        config=config 
    )