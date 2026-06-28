"""
examly_coding.py — The coding-question workflow prompt.

Simplified: the agent now calls ONE action (solve_coding_with_retry) which handles
the entire solve → compile → check → fix → retry loop internally.
The agent just needs to pass the problem text and then submit.
"""

CODING_WORKFLOW = """# CODING QUESTIONS (DSA)
When you encounter a coding question, follow this EXACT sequence. The default language is Python 3.

## Step 1 — UNDERSTAND
Read the ENTIRE problem: title, description, examples, constraints, input/output format.
Copy the COMPLETE problem text — every detail matters for the solver.

## Step 2 — SET LANGUAGE
Ensure the editor language dropdown is set to 'Python 3' (or whatever language the problem requires).

## Step 3 — SOLVE (Self-Healing Loop)
Call `solve_coding_with_retry` with the COMPLETE problem text.
This action handles EVERYTHING automatically:
  - Generates optimal code using a powerful reasoning model
  - Types the code into the Monaco editor
  - Clicks 'Compile & Run'
  - Reads ALL test case results
  - If any test case fails, it analyzes the failure and generates a fix
  - Retries up to 3 times total with different strategies
  - Returns the final verdict

DO NOT call inject_code_to_editor or solve_coding_question separately.
DO NOT try to read test case results yourself — the solver does this internally.
Just call solve_coding_with_retry and wait for it to finish.

## Step 4 — SUBMIT
Read the returned verdict message:
  - "ALL TEST CASES PASSED" → Click 'Submit Code' immediately. Done!
  - "BEST ATTEMPT after 3 tries" → Click 'Submit Code' anyway (submit what we have). Move on.

NEVER attempt more than what solve_coding_with_retry already tried. It handles all retries internally.

## READING THE VERDICT
The action returns a clear message telling you exactly what to do. Follow it literally.
- If it says "Click Submit Code" → find and click the Submit Code button.
- After submitting, move to the next question immediately."""
