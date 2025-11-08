# ai_agent.py
"""
AI Agent Module
Responsible for calling OpenAI API for intelligent decision making
"""

import os
import json
from openai import OpenAI


# Initialize the OpenAI client
try:
    # OpenAI client uses the environment variable OPENAI_API_KEY
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
except KeyError:
    print("ERROR: OPENAI_API_KEY environment variable is not set.")
    print("Environment example on Windows:  set OPENAI_API_KEY=sk-...")
    raise SystemExit(1)


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
