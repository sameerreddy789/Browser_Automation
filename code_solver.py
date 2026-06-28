"""
code_solver.py — Self-Healing DSA Code Solver

Full self-healing retry loop architecture:
  Attempt 1 (Gemini Flash Lite)  →  Initial solve
  Attempt 2 (Gemini + FIX_PROMPT) →  Surgical bug fix
  Attempt 3 (Llama 3.1 70B fallback + FIX_PROMPT) →  Stronger model

Each attempt:  generate code → type into Monaco → Compile & Run → scrape verdict
If ACCEPTED → save to answer bank → done
If FAILED   → feed error details back into the next attempt

The browser interaction (typing code, clicking Compile & Run, reading results)
is handled by callback functions passed in from main.py's controller actions.
This keeps code_solver.py decoupled from Playwright internals.

Usage:
    from code_solver import solve_with_retry, solve_problem, fix_solution

    # Full self-healing loop (called from controller action)
    code = await solve_with_retry(problem_statement, type_code_fn, get_verdict_fn, language)

    # Standalone (legacy compatibility)
    code = await solve_problem("Given an array...", language="python")
    fixed = await fix_solution("Given an array...", "def solve()...", "WA on test 2")
"""

import os
import re
import time
from groq import Groq
from loguru import logger

logger = logger.bind(name="browser_use.code_solver")

# ── Config ──────────────────────────────────────────────────────────────────
CODING_MODEL = os.getenv("CODING_MODEL", "llama-3.3-70b-versatile")
FALLBACK_MODEL = os.getenv("CODING_FALLBACK_MODEL", "llama-3.3-70b-versatile")
MAX_RETRIES = 3  # max attempts before giving up

_client = None


def _get_client():
    """Lazy-initialize the Groq client."""
    global _client
    if _client is None:
        _client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    return _client


# Also support Gemini as a caller
_gemini_client = None


def _get_gemini_client():
    """Lazy-initialize the Gemini client."""
    global _gemini_client
    if _gemini_client is None:
        from google import genai
        _gemini_client = genai.Client()
    return _gemini_client


# ── Prompt Templates ────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert competitive programmer. Your sole task is to write a correct, complete, and optimally efficient solution for the given coding problem.

═══════════════════════════════════════════════════
PHASE 1 — PARSE THE PROBLEM (do this silently)
═══════════════════════════════════════════════════
Extract and confirm before writing any code:
  - What exactly is being asked (precise task, not a paraphrase)
  - Input format: number of lines, data types, structure per line
  - Output format: exactly what to print, any trailing newline or space rules
  - Every sample test case: map each input → expected output
  - Constraints: size of N, value ranges, implicit time limit (default: 2 seconds)

═══════════════════════════════════════════════════
PHASE 2 — CHOOSE THE RIGHT ALGORITHM
═══════════════════════════════════════════════════
Pick the approach based on N:
  N <= 10^3      → O(N^2) acceptable
  N <= 10^5      → O(N log N) required
  N <= 10^6      → O(N) required
  N <= 10^18     → O(log N) or math formula only

Prefer these patterns in order of fit:
  - Two pointers / sliding window
  - Binary search (on answer or value)
  - Prefix sums / difference arrays
  - Monotonic stack or deque
  - Greedy (only if provably correct)
  - BFS / DFS / Dijkstra for graphs
  - Dynamic programming (1D or 2D)
  - Math / number theory

═══════════════════════════════════════════════════
PHASE 3 — WRITE THE CODE
═══════════════════════════════════════════════════
Language: {language} only.

MANDATORY rules:
  1. For Python: Always start with:
       import sys
       input = sys.stdin.readline
  2. For Python with multiple outputs use:
       sys.stdout.write("\\n".join(results) + "\\n")
     Never call print() in a hot loop.
  3. Handle edge cases explicitly:
       - N = 0 or empty input
       - N = 1
       - All elements identical
       - Max constraint values
       - Negative numbers if allowed
  4. No debug prints. No logging. No TODO comments. No stubs.
  5. No unused imports.
  6. Complete, runnable code only.

═══════════════════════════════════════════════════
PHASE 4 — TRACE EVERY SAMPLE TEST CASE
═══════════════════════════════════════════════════
Mentally execute your code on EACH sample before finalizing:
  - Feed each sample input through your logic line by line
  - Confirm output matches character for character
  - If any sample fails → fix and re-trace

═══════════════════════════════════════════════════
PHASE 5 — OUTPUT RULES (CRITICAL)
═══════════════════════════════════════════════════
  - Raw code only
  - Zero markdown — no ```, no ```python, no language tags
  - Zero explanation before or after the code
  - Zero preamble like "Here is the solution" or "Sure!"
  - First character of your response = first character of the code

The code is typed character-by-character into a Monaco editor.
Any non-code character corrupts and breaks the submission.

═══════════════════════════════════════════════════
HARD CONSTRAINTS
═══════════════════════════════════════════════════
X No markdown of any kind
X No input() for Python — always sys.stdin.readline
X No bare print() in hot loops
X No incomplete functions or stubs
X No code that fails your own sample trace
X Output format must match exactly — spacing, newlines, case
X DO NOT use f-strings — they cause injection errors in the Monaco editor. Use str() + concatenation or .format() instead.
X DO NOT use triple quotes or backticks inside the code.

PROBLEM:
{problem_statement}"""


FIX_PROMPT = """You are an expert competitive programmer performing a surgical bug fix.

A solution was submitted to a judge and FAILED. Your job is to analyze
the exact failure, identify the root cause, fix it, and return the corrected code.

═══════════════════════════════════════════════════
ORIGINAL PROBLEM
═══════════════════════════════════════════════════
{problem_statement}

═══════════════════════════════════════════════════
FAILED CODE (what was submitted)
═══════════════════════════════════════════════════
{failed_code}

═══════════════════════════════════════════════════
JUDGE VERDICT & ERROR DETAILS
═══════════════════════════════════════════════════
{error_details}

═══════════════════════════════════════════════════
DIAGNOSIS RULES — follow in order
═══════════════════════════════════════════════════
Map the verdict to the most likely root cause:

WRONG ANSWER (WA):
  -> Off-by-one error in loop bounds or indexing
  -> Wrong formula or operator (e.g. // vs /, + vs -, < vs <=)
  -> Output format mismatch (extra space, missing newline, wrong case)
  -> Incorrect handling of edge case (N=0, N=1, negatives, duplicates)
  -> Greedy choice is wrong — reconsider with DP or brute force
  -> Integer overflow not an issue in Python but check float precision
  -> Reading input incorrectly (wrong number of values per line)

TIME LIMIT EXCEEDED (TLE):
  -> O(N^2) inside an O(N) loop — need a better data structure
  -> Redundant recomputation — add memoization or precompute
  -> Using list for O(N) lookups — switch to set or dict
  -> Recursion without memoization — switch to iterative DP
  -> sys.stdin not used — input() is too slow for large N
  -> print() called in a loop — batch output with sys.stdout.write

RUNTIME ERROR (RE):
  -> Index out of bounds — check all list accesses
  -> Division by zero — add guard condition
  -> RecursionError — increase sys.setrecursionlimit or go iterative
  -> KeyError / ValueError — validate input parsing
  -> Stack overflow on deep recursion — rewrite iteratively

PRESENTATION ERROR (PE):
  -> Trailing space at end of line
  -> Extra blank line at end of output
  -> Printing int vs float (e.g. 3 vs 3.0)

═══════════════════════════════════════════════════
FIX RULES
═══════════════════════════════════════════════════
  1. Fix ONLY what is broken — do not rewrite working logic
  2. If the algorithm itself is wrong, replace it entirely with the correct one
  3. Re-trace ALL sample test cases on the fixed code before outputting
  4. If a sample still fails after your fix -> fix again before outputting
  5. The fixed code must handle ALL edge cases, not just the one that failed

═══════════════════════════════════════════════════
OUTPUT RULES (IDENTICAL TO INITIAL SOLVE)
═══════════════════════════════════════════════════
  - Raw code only
  - Zero markdown — no ```, no ```python
  - Zero explanation before or after
  - First character of response = first character of code
  - This is typed into Monaco editor — any extra character breaks it
  - DO NOT use f-strings — they cause injection errors. Use str() + concatenation or .format() instead.
  - DO NOT use triple quotes or backticks inside the code.

HARD CONSTRAINTS:
X No markdown
X No input() for Python — always sys.stdin.readline
X No print() in hot loops
X No stubs or incomplete logic
X No code that fails any sample test case"""


RETRY_PROMPT = """You are an expert competitive programmer. A previous solution to this problem FAILED.
You must solve it using a COMPLETELY DIFFERENT algorithmic approach.

═══════════════════════════════════════════════════
PROBLEM
═══════════════════════════════════════════════════
{problem_statement}

═══════════════════════════════════════════════════
PREVIOUS FAILED CODE (DO NOT USE THIS SAME APPROACH)
═══════════════════════════════════════════════════
{failed_code}

═══════════════════════════════════════════════════
WHY IT FAILED (all accumulated errors)
═══════════════════════════════════════════════════
{all_errors}

═══════════════════════════════════════════════════
CRITICAL INSTRUCTIONS
═══════════════════════════════════════════════════
The previous approach is wrong. You must:
1. Identify WHY the previous approach fails.
2. Choose a FUNDAMENTALLY DIFFERENT algorithm.
3. Consider these alternative strategy swaps:
   - Previous was greedy -> try DP, binary search, or two-pointer
   - Previous was DP -> try greedy with proof, or a different DP state definition
   - Previous was brute force -> use an optimal algorithm (segment tree, BFS, etc.)
   - Previous was sorting-based -> try hash map, prefix sum, or monotonic stack
   - Previous was iterative -> try recursive with memoization
4. Pay EXTREME attention to the I/O format — match it EXACTLY.
5. Handle ALL edge cases, especially the ones that caused the failure.

═══════════════════════════════════════════════════
OUTPUT RULES
═══════════════════════════════════════════════════
  - Raw code only — zero markdown, zero explanation
  - First character of response = first character of code
  - DO NOT use f-strings. Use str() + concatenation or .format() instead.
  - DO NOT use triple quotes or backticks inside the code.
  - For Python: always use sys.stdin.readline, not input()

X No markdown of any kind
X No stubs or incomplete logic
X No code that fails any sample test case"""


# ── Code Extraction ─────────────────────────────────────────────────────────

def _extract_code(response_text: str, language: str = "python") -> str:
    """
    Extract clean, ready-to-paste code from the AI response.
    Strips markdown fences and preamble text.
    """
    # Pattern 1: Code in markdown fences with language tag
    lang_aliases = {
        "cpp": r"(?:cpp|c\+\+|cc|cxx)",
        "c": r"(?:c)",
        "python": r"(?:python|py|python3)",
        "java": r"(?:java)",
    }
    lang_pattern = lang_aliases.get(language, language)

    match = re.search(
        rf"```{lang_pattern}\s*\n(.*?)```",
        response_text,
        re.DOTALL | re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()

    # Pattern 2: Generic code block (no language specified)
    match = re.search(r"```\s*\n(.*?)```", response_text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Pattern 3: No code blocks — try to find code by language markers
    lines = response_text.strip().split("\n")
    code_start_markers = [
        # Python markers
        "def ", "import ", "from ", "class ",
        # C/C++ markers
        "#include", "using namespace", "int main", "struct ",
        "void ", "typedef ", "#define", "#pragma",
        # Java markers
        "public class", "import java",
    ]

    code_started = False
    code_lines = []

    for line in lines:
        stripped = line.strip()
        if not code_started:
            if any(stripped.startswith(marker) for marker in code_start_markers):
                code_started = True
                code_lines.append(line)
        else:
            if stripped and not any(c in stripped for c in [
                "{", "}", ";", "(", ")", "#", "//", "/*", "*/", "=", "+", "-",
                "<", ">", "[", "]", '"', "'", "return", "if", "else", "for",
                "while", "def", "import", "class", "print", "input"
            ]):
                if (len(stripped) > 40 and " " in stripped
                        and not stripped.startswith("#")
                        and not stripped.startswith("//")):
                    break
            code_lines.append(line)

    if code_lines:
        return "\n".join(code_lines).strip()

    # Last resort: return the entire response
    return response_text.strip()


def _get_response_text(response) -> str:
    try:
        return response.choices[0].message.content or ""
    except Exception:
        return ""


def _lang_name(language: str) -> str:
    return {
        "cpp": "C++", "c": "C", "python": "Python 3", "java": "Java",
    }.get(language, language)


# ── Model Callers ────────────────────────────────────────────────────────────

def _call_groq(prompt: str, model: str = None) -> str:
    """Call Groq API (Llama or other model). Returns raw text."""
    client = _get_client()
    use_model = model or CODING_MODEL
    response = client.chat.completions.create(
        model=use_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    return _get_response_text(response)


def _call_gemini(prompt: str) -> str:
    """Call Gemini 2.5 Flash. Returns raw text."""
    client = _get_gemini_client()
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config={"temperature": 0.1, "max_output_tokens": 4096},
    )
    return response.text.strip() if response.text else ""


def _call_model(prompt: str, attempt: int = 1) -> str:
    """
    Smart model selection based on attempt number:
      Attempt 1: Groq (primary model — llama-3.3-70b)
      Attempt 2: Groq (same model, different prompt — FIX_PROMPT)
      Attempt 3: Gemini Flash Lite (different model entirely for diversity)

    Falls back across providers on any exception.
    """
    if attempt <= 2:
        try:
            return _call_groq(prompt)
        except Exception as e:
            logger.warning(f"Groq failed ({e}), falling back to Gemini")
            try:
                return _call_gemini(prompt)
            except Exception as e2:
                logger.error(f"Both Groq and Gemini failed: {e2}")
                return ""
    else:
        # Attempt 3: try Gemini first for model diversity
        try:
            return _call_gemini(prompt)
        except Exception as e:
            logger.warning(f"Gemini failed on attempt 3 ({e}), falling back to Groq")
            try:
                return _call_groq(prompt, model=FALLBACK_MODEL)
            except Exception as e2:
                logger.error(f"Both models failed on attempt 3: {e2}")
                return ""


# ── Core Self-Healing Loop ──────────────────────────────────────────────────

async def solve_with_retry(
    problem_statement: str,
    type_code_fn,
    compile_and_get_verdict_fn,
    language: str = "python",
) -> dict:
    """
    Full self-healing solve loop that drives the browser directly.

    This is the heart of the new architecture. Instead of letting the
    agent's natural language planning drive retries (which is flaky),
    this function runs a deterministic Python loop:

        solve → type into editor → compile → check verdict → fix → repeat

    Args:
        problem_statement:          Full problem text including samples/constraints.
        type_code_fn:               async callable(code: str) → None
                                    Clears editor and types code into Monaco.
        compile_and_get_verdict_fn: async callable() → dict
                                    Clicks Compile & Run, waits for results,
                                    returns dict with keys:
                                      verdict: str ("ACCEPTED", "WA", "TLE", "RE", "CE", "PE")
                                      details: str (human-readable error summary)
                                      passed: int (number of test cases passed)
                                      total: int (total test cases)
        language:                   Programming language (default: "python").

    Returns:
        dict with keys:
          code: str       — final code (best attempt)
          verdict: str    — final verdict
          attempts: int   — number of attempts used
          passed: int     — test cases passed on final attempt
          total: int      — total test cases
    """
    lang_name = _lang_name(language)
    current_code = None
    all_errors = []  # accumulate all failure details across attempts
    best_result = {"code": "", "verdict": "NOT_ATTEMPTED", "attempts": 0, "passed": 0, "total": 0}

    for attempt in range(1, MAX_RETRIES + 1):
        logger.info(f"{'='*50}")
        logger.info(f"[SELF-HEAL] Attempt {attempt}/{MAX_RETRIES} ({lang_name})")
        logger.info(f"{'='*50}")

        # ── Generate code ────────────────────────────────────────────────
        if attempt == 1:
            prompt = SYSTEM_PROMPT.format(
                language=lang_name,
                problem_statement=problem_statement,
            )
        elif attempt == 2:
            error_summary = "\n---\n".join(all_errors)
            prompt = FIX_PROMPT.format(
                problem_statement=problem_statement,
                failed_code=current_code,
                error_details=error_summary,
            )
        else:
            error_summary = "\n---\n".join(all_errors)
            prompt = RETRY_PROMPT.format(
                problem_statement=problem_statement,
                failed_code=current_code,
                all_errors=error_summary,
            )

        raw = _call_model(prompt, attempt=attempt)

        if not raw:
            logger.error(f"[SELF-HEAL] Empty response on attempt {attempt}")
            continue

        current_code = _extract_code(raw, language)
        logger.info(f"[SELF-HEAL] Generated code ({len(current_code)} chars, {current_code.count(chr(10)) + 1} lines)")

        # ── Type into editor ─────────────────────────────────────────────
        logger.info(f"[SELF-HEAL] Injecting code into Monaco editor...")
        await type_code_fn(current_code)

        # ── Compile & get verdict ────────────────────────────────────────
        logger.info(f"[SELF-HEAL] Compiling and checking test cases...")
        verdict_info = await compile_and_get_verdict_fn()

        verdict = verdict_info.get("verdict", "UNKNOWN")
        details = verdict_info.get("details", "")
        passed = verdict_info.get("passed", 0)
        total = verdict_info.get("total", 0)

        logger.info(f"[SELF-HEAL] Verdict: {verdict} ({passed}/{total} test cases)")

        best_result = {
            "code": current_code,
            "verdict": verdict,
            "attempts": attempt,
            "passed": passed,
            "total": total,
        }

        # ── Check if accepted ────────────────────────────────────────────
        if verdict == "ACCEPTED" or (total > 0 and passed == total):
            logger.info(f"[SELF-HEAL] ACCEPTED on attempt {attempt}!")
            return best_result

        # ── Log failure for next attempt ─────────────────────────────────
        error_entry = f"Attempt {attempt} — Verdict: {verdict}\n{details}"
        all_errors.append(error_entry)
        logger.warning(f"[SELF-HEAL] Failed: {verdict}. {details}")

        if attempt < MAX_RETRIES:
            logger.info(f"[SELF-HEAL] Retrying with {'fix prompt' if attempt == 1 else 'different algorithm'}...")

    # ── All retries exhausted ────────────────────────────────────────────
    logger.error(f"[SELF-HEAL] FAILED after {MAX_RETRIES} attempts. Submitting best attempt.")
    return best_result


# ── Legacy Standalone Functions (backward compatibility) ─────────────────────

async def solve_problem(problem_statement: str, language: str = "python") -> str:
    """
    Solve a coding problem (standalone, no browser interaction).
    Used by the multi_run.py review phase and as a fallback.
    """
    lang_name = _lang_name(language)

    prompt = SYSTEM_PROMPT.format(
        language=lang_name,
        problem_statement=problem_statement,
    )

    try:
        logger.info(f"[CODE SOLVER] Generating {lang_name} solution with {CODING_MODEL}...")
        raw = _call_model(prompt, attempt=1)

        if not raw:
            logger.error(f"[CODE SOLVER] Empty response from {CODING_MODEL}")
            return "# Error: Empty response from code solver"

        code = _extract_code(raw, language)
        logger.info(f"[CODE SOLVER] Generated solution ({len(code)} chars, {code.count(chr(10)) + 1} lines)")
        return code

    except Exception as e:
        logger.error(f"[CODE SOLVER] Failed to solve problem: {e}")
        return f"# Error: Code solver failed — {str(e)}"


async def fix_solution(problem_statement: str, current_code: str,
                       failure_details: str, language: str = "python") -> str:
    """
    Fix a failing solution (standalone, no browser interaction).
    Used by the multi_run.py review phase.
    """
    prompt = FIX_PROMPT.format(
        problem_statement=problem_statement,
        failed_code=current_code,
        error_details=failure_details,
    )

    try:
        logger.info(f"[CODE SOLVER] Analyzing failure and generating fix with {CODING_MODEL}...")
        raw = _call_model(prompt, attempt=2)

        if not raw:
            logger.error("[CODE SOLVER] Empty response when trying to fix solution")
            return current_code

        code = _extract_code(raw, language)
        logger.info(f"[CODE SOLVER] Generated fix ({len(code)} chars, {code.count(chr(10)) + 1} lines)")
        return code

    except Exception as e:
        logger.error(f"[CODE SOLVER] Failed to fix solution: {e}")
        return current_code


async def solve_problem_retry(problem_statement: str, previous_code: str,
                              all_failure_details: str, language: str = "python") -> str:
    """
    Last-resort retry with a different algorithm (standalone, no browser).
    Used by the multi_run.py review phase.
    """
    prompt = RETRY_PROMPT.format(
        problem_statement=problem_statement,
        failed_code=previous_code,
        all_errors=all_failure_details,
    )

    try:
        logger.info(f"[CODE SOLVER] Last resort — different approach with {CODING_MODEL}...")
        raw = _call_model(prompt, attempt=3)

        if not raw:
            logger.error("[CODE SOLVER] Empty response on retry attempt")
            return previous_code

        code = _extract_code(raw, language)
        logger.info(f"[CODE SOLVER] Generated alternative solution ({len(code)} chars, {code.count(chr(10)) + 1} lines)")
        return code

    except Exception as e:
        logger.error(f"[CODE SOLVER] Retry failed: {e}")
        return previous_code
