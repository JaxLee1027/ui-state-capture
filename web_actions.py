# web_actions.py
"""
Web Actions Module
Responsible for executing specific actions on the webpage
"""

import os
from playwright.sync_api import Page


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
