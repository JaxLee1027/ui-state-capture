# agent.py
# Final consolidated agent script for Linear issue creation

import os
import time
import json
import argparse
from playwright.sync_api import sync_playwright, Page
from openai import OpenAI

# --- Configuration ---
AUTH_FILE_PATH = "linear_auth.json"
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
    [THE FINAL, FINAL FIX] This version adds a check for [role="menu"].
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


def think(goal: str, dom: str, history: list) -> dict:
    """
    Think phase.
    Sends the current goal, DOM, and action history to the LLM
    and receives a structured action description in JSON form.
    """

    history_string = "\n".join(history)

    prompt = f"""
    We are an AI agent.
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
    - Editable text fields appear as elements formatted like:
    <TEXT-INPUT data-agent-id="..." label="..."></TEXT-INPUT>
    - The "type" action must only be used on elements formatted as <TEXT-INPUT ...>.
    - Never use the "type" action on elements formatted as <CHECKBOX ...> or on any BUTTON.
    - When the goal mentions typing the issue title, and at least one <TEXT-INPUT ...> element exists,
    the agent must choose a "type" action instead of "fail" or clicking "Create issue".
    - If multiple <TEXT-INPUT ...> elements exist, prefer the one whose label contains words such as
    "issue" or "title" (case-insensitive). If none match, choose the most reasonable text input
    near the center of the modal.
    - If no <TEXT-INPUT ...> element is present yet, but there are clickable elements that may reveal
    such an input (for example a button that opens a form), the agent should click one of them
    instead of returning "fail".
    - The "fail" action is a last resort when there is truly no reasonable clickable element and
    no text input that can progress the goal.

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


def run_agent_loop(goal: str, task_name: str, workspace_url: str, anchor_selector: str):
    """
    Outer loop that coordinates Observe -> Think -> Act steps.
    Loads a stored Linear session, navigates to the workspace,
    and runs up to a fixed number of steps.
    """

    if not os.path.exists(AUTH_FILE_PATH):
        print(
            f"Error: auth file '{AUTH_FILE_PATH}' not found. "
            f"Run the login script that creates this file before starting the agent."
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
        context = browser.new_context(storage_state=AUTH_FILE_PATH)
        page = context.new_page()

        print(f"Navigating to workspace: {workspace_url}")
        page.goto(workspace_url)

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
                page.wait_for_timeout(1000)

                # 1. Observe
                simplified_dom = get_simplified_dom(page)
                if not simplified_dom:
                    print("Simplified DOM is empty. Stopping agent.")
                    break

                # 2. Think
                action = think(goal, simplified_dom, action_history)

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
            print("Capturing a screenshot of the critical error state...")
            page.screenshot(path=os.path.join(task_dir, "critical_error.png"))

        print("Pausing for 5 seconds before closing the browser.")
        page.wait_for_timeout(5000)
        browser.close()


if __name__ == "__main__":
    """
    Entry point.
    Parses command-line arguments and starts the agent loop.
    """

    parser = argparse.ArgumentParser(
        description="Run the AI agent on a Linear web task."
    )

    parser.add_argument(
        "--url",
        type=str,
        required=True,
        help="Specific Linear workspace URL where the agent starts.",
    )

    parser.add_argument(
        "--selector",
        type=str,
        default='text="Inbox"',
        help="Stable anchor selector that indicates the dashboard is loaded.",
    )

    parser.add_argument(
        "--goal",
        type=str,
        default=(
            "Find the button to create a new issue and click it. "
            "Then, in the modal that opens, type 'My First AI Issue' into the title field."
        ),
        help="High-level task goal for the agent.",
    )

    parser.add_argument(
        "--task-name",
        type=str,
        default="linear_create_issue_test_1",
        help="Folder name inside ./dataset/ for storing screenshots.",
    )

    args = parser.parse_args()

    run_agent_loop(
        goal=args.goal,
        task_name=args.task_name,
        workspace_url=args.url,
        anchor_selector=args.selector,
    )
