"""
examly_submit.py — Final submission gate prompt.

Enforces the multi-section check and the END-text typing for the final submit.
"""

SUBMISSION_GATE = """# FINAL SUBMISSION GATE
You are FORBIDDEN from clicking 'Submit Test' until you have:
1. Checked the 'Section' dropdown at the top of the page.
2. Completed EVERY section (e.g., if it says 'Section: 1/2', you MUST switch to
   section 2 and complete it too).
3. Verified there are no unanswered questions in any section.

Only then: Click 'Submit Test'.
When asked to type 'END', type exactly 'END' (all uppercase, no spaces) using the `human_type` action.
NEVER use standard instant text filling tools. If the typing fails to enable the final submit button, run this
via 'evaluate':
    const endInput = Array.from(document.querySelectorAll('input')).find(el => el.placeholder.includes('END') || el.type === 'text');
    if (endInput) {
        endInput.focus();
        endInput.value = '';
        // If JS fallback is needed, simulate typing
        for (let char of 'END') {
            const e = new KeyboardEvent('keydown', { key: char });
            endInput.dispatchEvent(e);
            endInput.value += char;
            endInput.dispatchEvent(new Event('input', { bubbles: true }));
        }
    }"""
