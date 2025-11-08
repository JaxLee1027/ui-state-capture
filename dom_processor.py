# dom_processor.py
"""
DOM Processing Module
Responsible for extracting and simplifying webpage DOM structure for AI decision making
"""

from playwright.sync_api import Page


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
