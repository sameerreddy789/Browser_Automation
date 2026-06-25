"""
examly_coding.py — The coding-question workflow prompt.

Clear, structured, single source of truth for how to handle a DSA question:
solve once → verify → fix if needed → retry once → submit best and move on.
Hard-caps at 3 attempts to avoid the 30-minute-per-3-questions problem.
"""

CODING_WORKFLOW = """# CODING QUESTIONS (DSA)
When you encounter a coding question, follow this EXACT sequence. The default language is Python 3.

## Step 1 — UNDERSTAND
Read the ENTIRE problem: title, description, examples, constraints, input/output format.
Copy the COMPLETE problem text — every detail matters.

## Step 2 — SOLVE (Tier 1)
Call `solve_coding_question` with the COMPLETE problem text. This uses a powerful
reasoning model and returns optimal code. Do NOT write code yourself.

## Step 3 — INJECT
Ensure the editor language dropdown is set to 'Python 3'.
Call `inject_code_to_editor` with the returned code. NEVER type code line-by-line.

## Step 4 — VERIFY
Click 'Compile & Run'. Read ALL test case results:
- ALL PASS → Click 'Submit Code' → done, move to the next question.
- ANY FAIL → go to Step 5.

## Step 5 — FIX (Tier 2)
Read the EXACT expected vs actual output for each failing test case.
Call `fix_coding_solution` with: problem, current code, failure details.
Inject fixed code → Compile & Run.
- PASS → Submit Code → done.
- STILL FAIL → go to Step 6.

## Step 6 — RETRY (Tier 3)
Call `retry_coding_solution` with: problem, failing code, ALL accumulated failures.
This tries a completely different algorithm. Inject → Compile & Run.
- PASS → Submit Code → done.
- STILL FAIL → go to Step 7.

## Step 7 — MOVE ON (HARD LIMIT)
MAXIMUM 3 attempts (1 solve + 1 fix + 1 retry). After the 3rd attempt fails,
Submit your best attempt IMMEDIATELY and move to the next question.
DO NOT attempt a 4th time. Time is critical.

## READING TEST RESULTS
- 'Time Limit Exceeded' → algorithm too slow, needs a fundamentally different approach.
- 'Runtime Error' → array out of bounds, division by zero, stack overflow.
- 'Wrong Answer' → logic or I/O format incorrect.
When calling fix/retry, include expected AND actual output for every failing case."""
