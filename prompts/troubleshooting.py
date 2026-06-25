"""
troubleshooting.py — Self-healing prompts (modals, disabled buttons, CAPTCHAs).

Kept as its own module so it doesn't clutter the core workflow sections. These
are recovery procedures the agent applies only when something goes wrong.
"""

TROUBLESHOOTING = """# TROUBLESHOOTING & SELF-HEALING (apply only when something goes wrong)

## MONACO CODE EDITOR
Always use `inject_code_to_editor`. Do NOT use `evaluate` with raw code strings (unescaped characters cause syntax errors).

## HUMAN TYPING EVASION (CRITICAL)
NEVER use instant text filling, value insertion, or clipboard pasting (like element.fill() or element.setValue() commands). To type text into inputs, search bars, or textareas, ALWAYS use `human_type`. To inject code, ALWAYS use `inject_code_to_editor`. Both actions simulate realistic human typing character-by-character with random delays (80ms - 120ms) to bypass bot detection.

## BLOCKING MODALS & DIALOGS
If a warning/modal/overlay blocks the screen, click 'Yes'/'Okay'/'Close'.
If it's stuck, force-remove it via 'evaluate':
    const overlays = document.querySelectorAll('.modal-backdrop, .modal, [class*="modal"], [id*="modal"]');
    overlays.forEach(el => el.remove());
    document.body.classList.remove('modal-open');

## DISABLED BUTTONS
If 'Compile & Run' or 'Submit Code' stay disabled after entering code, force-enable via 'evaluate':
    const compileBtn = document.getElementById('programme-compile');
    if (compileBtn) compileBtn.disabled = false;
    const submitBtn = document.getElementById('tt-footer-submit-answer') || document.getElementById('tt-footer-submit-ans');
    if (submitBtn) submitBtn.disabled = false;

## CAPTCHA & ANTI-BOT
For an image text CAPTCHA: use `solve_captcha_image` with the image selector, then
type the result into the text field. On aggressive anti-bot (e.g. Cloudflare), use
`human_click` and `human_hover` instead of default clicks.

## VISUAL GROUNDING (LAST RESORT for selector issues)
If CSS selectors fail or the layout looks unexpected:
- `visual_click`: describe the element to click (e.g., "the blue Login button").
- `visual_find`: get pixel coordinates without clicking.
- `visual_scroll`: scroll until a described element is visible.
- `visual_describe_page`: get an AI description of everything on screen.

## ASK FOR HELP (LAST RESORT)
If you absolutely cannot solve a blocker, call `request_user_input` with a clear
description of what's stuck. A human OR an AI consultant (via API) will respond
in the terminal to unblock you."""
