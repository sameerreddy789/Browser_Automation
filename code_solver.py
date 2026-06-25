"""
code_solver.py — Dedicated DSA/Competitive Coding Solver

Uses a powerful reasoning model (gemini-2.5-flash by default, with thinking enabled)
specifically for solving coding questions. This is separate from the navigation LLM
(gemini-3.1-flash-lite) because coding problems require deep algorithmic reasoning
that lightweight models can't handle.

Two-brain architecture:
- Navigation brain (lite model): Clicks buttons, reads pages, navigates the website
- Coding brain (this module):    Solves DSA problems with optimal algorithms

The model is configurable via the CODING_MODEL environment variable.

Usage:
    from code_solver import solve_problem, fix_solution

    # Solve a new problem
    code = await solve_problem("Given an array...", language="python")

    # Fix a failing solution
    fixed_code = await fix_solution(
        problem="Given an array...",
        current_code="...",
        failure="Expected: 5, Got: 3",
        language="python",
    )
"""

import os
import re
from google import genai
from loguru import logger

logger = logger.bind(name="browser_use.code_solver")

# The coding model — override via CODING_MODEL env var if needed.
# gemini-2.5-flash supports deep thinking/reasoning and is far stronger than
# the flash-lite model used for navigation.
CODING_MODEL = os.getenv("CODING_MODEL", "gemini-2.5-flash")

# Lazy-initialized Gemini client (reuses the same GOOGLE_API_KEY from .env)
_client = None


def _get_client():
    """Lazy-initialize the Gemini client."""
    global _client
    if _client is None:
        _client = genai.Client()
    return _client


def _build_generate_config() -> dict:
    """
    Build the generation config for the coding model.

    Enables thinking so the model reasons through the algorithm before writing
    code, and uses a low temperature for consistent, precise solutions.
    """
    try:
        # google-genai supports ThinkingConfig for thinking-capable models.
        from google.genai import types
        return {
            "temperature": 0.2,
            "thinking_config": types.ThinkingConfig(include_thoughts=False),
        }
    except Exception:
        # Older SDK or non-thinking model — fall back to temperature only.
        return {"temperature": 0.2}


def _extract_code(response_text: str, language: str = "python") -> str:
    """
    Extract clean, ready-to-paste code from the AI response.

    The AI might return code wrapped in markdown fences like:
        ```python
        def solve():
            ...
        ```

    This function strips all that and returns just the raw code.
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

    # Pattern 3: No code blocks — try to find code by looking for language markers
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
            # Stop if we hit obvious non-code text (explanation paragraphs)
            if stripped and not any(c in stripped for c in ["{", "}", ";", "(", ")", "#", "//", "/*", "*/", "=", "+", "-", "<", ">", "[", "]", '"', "'", "return", "if", "else", "for", "while", "def", "import", "class", "print", "input"]):
                if len(stripped) > 40 and " " in stripped and not stripped.startswith("#") and not stripped.startswith("//"):
                    break
            code_lines.append(line)

    if code_lines:
        return "\n".join(code_lines).strip()

    # Last resort: return the entire response (maybe the model returned just code)
    return response_text.strip()


def _get_response_text(response) -> str:
    """
    Safely extract text from a Gemini API response.
    Handles both standard and thinking model response formats.
    """
    try:
        return response.text
    except Exception:
        pass

    try:
        for candidate in response.candidates:
            for part in reversed(candidate.content.parts):
                if hasattr(part, "text") and part.text:
                    return part.text
    except Exception:
        pass

    return ""


def _lang_name(language: str) -> str:
    return {
        "cpp": "C++", "c": "C", "python": "Python", "java": "Java",
    }.get(language, language)


async def solve_problem(problem_statement: str, language: str = "python") -> str:
    """
    Solve a coding problem using a powerful reasoning model.

    This is the main entry point. Pass the COMPLETE problem statement (including
    sample inputs/outputs and constraints) and get back clean, optimal code.

    Args:
        problem_statement: The COMPLETE problem text including sample I/O and constraints.
        language: Programming language (default: "python").

    Returns:
        Clean, ready-to-paste code string (no markdown, no explanations).
    """
    client = _get_client()
    lang_name = _lang_name(language)

    prompt = f"""You are an expert competitive programmer (Codeforces Grandmaster level).
Solve this DSA problem in {lang_name}. Your solution MUST pass ALL test cases including hidden ones.

## PROBLEM
{problem_statement}

## REQUIREMENTS
- Language: {lang_name}
- Optimize for BOTH time AND space complexity.
- Read input from sys.stdin, write to standard print/output.
- Output EXACTLY what the problem asks — no extra text like "Enter:", "Result:", "Answer:".
- Match the output format PRECISELY (spaces, newlines, trailing whitespace all matter).
- Handle ALL edge cases (empty input, n=0, n=1, negative numbers, maximum constraints).

## COMPLEXITY BUDGET (determine required time complexity from constraints)
- n ≤ 20 → O(2^n) or O(n!) acceptable (brute force / backtracking)
- n ≤ 100 → O(n^3) acceptable
- n ≤ 10^3 → O(n^2) acceptable
- n ≤ 10^5 → need O(n log n) or better
- n ≤ 10^6 → need O(n) or O(n log n)
- n ≤ 10^9 → need O(log n) or O(1) (binary search / math)

## ALGORITHM PATTERN SELECTION
- Counting subsequences / subsets → DP (NOT brute force enumeration)
- Shortest path → BFS (unweighted) or Dijkstra (weighted)
- Subarray sum / window → Sliding window or prefix sums
- String matching → KMP or Z-algorithm (NOT O(n*m) naive)
- Palindrome → DP or Manacher's algorithm
- Range queries → Segment tree, BIT, or sparse table
- Greedy → sort + greedy selection with proof
- Tree DP → DFS with memoization
- Combinatorics → modular arithmetic with fast exponentiation

## {lang_name.upper()}-SPECIFIC RULES
- DO NOT use Python f-strings (e.g. f"value") — they cause injection errors in the Monaco editor. Use str() + concatenation or .format() instead.
- DO NOT use triple quotes or backticks inside the code.
- Keep the code concise and readable.

## THINK, THEN WRITE
1. What is the problem asking? (one sentence)
2. What are the constraints? → required time complexity?
3. What algorithm pattern matches?
4. Edge cases?
5. Trace through Sample Input to verify the approach.
6. Write the code.

## OUTPUT
Return ONLY the complete {lang_name} code. No explanations, no markdown fences, no comments about the approach — JUST the raw code that can be directly compiled and run."""

    try:
        logger.info(f"🧠 [CODE SOLVER]: Generating {lang_name} solution with {CODING_MODEL}...")

        response = client.models.generate_content(
            model=CODING_MODEL,
            contents=prompt,
            config=_build_generate_config(),
        )

        raw_response = _get_response_text(response)

        if not raw_response:
            logger.error(f"❌ [CODE SOLVER]: Empty response from {CODING_MODEL}")
            return "# Error: Empty response from code solver"

        code = _extract_code(raw_response, language)

        logger.info(f"✅ [CODE SOLVER]: Generated {lang_name} solution ({len(code)} chars, {code.count(chr(10)) + 1} lines)")
        return code

    except Exception as e:
        logger.error(f"❌ [CODE SOLVER]: Failed to solve problem: {e}")
        return f"# Error: Code solver failed — {str(e)}"


async def fix_solution(problem_statement: str, current_code: str,
                       failure_details: str, language: str = "python") -> str:
    """
    Fix a failing solution by analyzing the test case failure.

    Instead of blindly rewriting from scratch, this analyzes what went wrong
    and makes targeted fixes. If the algorithm is fundamentally wrong, it
    will replace it entirely.

    Args:
        problem_statement: The original problem text.
        current_code: The code that's currently failing.
        failure_details: What went wrong — expected vs actual output, error messages, etc.
        language: Programming language (default: "python").

    Returns:
        Fixed code string ready to paste.
    """
    client = _get_client()
    lang_name = _lang_name(language)

    prompt = f"""You are an expert competitive programmer debugging a failing DSA solution.
Analyze the failure and fix it.

## PROBLEM
{problem_statement}

## CURRENT FAILING CODE
{current_code}

## FAILURE DETAILS
{failure_details}

## SYSTEMATIC DEBUG CHECKLIST — check each one
1. I/O FORMAT: Does output match EXACTLY? Check spaces, newlines, trailing whitespace.
2. EDGE CASES: n=0, n=1, negative numbers, empty strings, single element.
3. OFF-BY-ONE: Loop bounds (< vs <=), array indexing (0-indexed vs 1-indexed).
4. WRONG ALGORITHM: Is the fundamental approach wrong? (e.g. greedy when DP is needed)
5. TIME LIMIT: If TLE reported, the algorithm is too slow — needs a fundamentally different approach.
6. RUNTIME ERROR: Array out of bounds, division by zero, stack overflow, unhandled None.
7. INPUT PARSING: Is ALL input being read correctly? Leftover data in the buffer?

## INSTRUCTIONS
- If the bug is a SMALL fix (format, edge case, off-by-one): make the targeted fix.
- If the algorithm is FUNDAMENTALLY WRONG: rewrite with the correct approach.
- Mentally trace your fixed code through the FAILING test case to verify it now produces the correct output.
- Ensure the fix does NOT break other previously-passing test cases.
- DO NOT use Python f-strings, triple quotes, or backticks.
- Keep the code concise (under ~60 lines).

## OUTPUT
Return ONLY the fixed {lang_name} code. No explanations — just the corrected code ready to compile and run."""

    try:
        logger.info(f"🔧 [CODE SOLVER]: Analyzing failure and generating fix with {CODING_MODEL}...")

        response = client.models.generate_content(
            model=CODING_MODEL,
            contents=prompt,
            config=_build_generate_config(),
        )

        raw_response = _get_response_text(response)

        if not raw_response:
            logger.error("❌ [CODE SOLVER]: Empty response when trying to fix solution")
            return current_code  # Return original if fix generation fails

        code = _extract_code(raw_response, language)

        logger.info(f"🔧 [CODE SOLVER]: Generated fix ({len(code)} chars, {code.count(chr(10)) + 1} lines)")
        return code

    except Exception as e:
        logger.error(f"❌ [CODE SOLVER]: Failed to fix solution: {e}")
        return current_code  # Return original code if fix fails


async def solve_problem_retry(problem_statement: str, previous_code: str,
                              all_failure_details: str, language: str = "python") -> str:
    """
    Last-resort retry: solve the problem from scratch using a completely different approach.

    This is called when both the initial solve and the fix attempts have failed.
    It explicitly tells the AI to try a DIFFERENT algorithm than what was used before.

    Args:
        problem_statement: The original problem text.
        previous_code: The code that was tried (to avoid using the same approach).
        all_failure_details: All accumulated failure information.
        language: Programming language (default: "python").

    Returns:
        New code string using a different approach.
    """
    client = _get_client()
    lang_name = _lang_name(language)

    prompt = f"""You are an expert competitive programmer. A previous solution to this problem FAILED.
You must solve it using a COMPLETELY DIFFERENT algorithmic approach.

## PROBLEM
{problem_statement}

## PREVIOUS FAILED CODE (DO NOT USE THIS SAME APPROACH)
{previous_code}

## WHY IT FAILED
{all_failure_details}

## CRITICAL
The previous approach is wrong. You must:
1. Identify WHY the previous approach fails.
2. Choose a FUNDAMENTALLY DIFFERENT algorithm.
3. Consider these alternative strategy swaps:
   - Previous was greedy → try DP, binary search, or two-pointer
   - Previous was DP → try greedy with proof, or a different DP state definition
   - Previous was brute force → use an optimal algorithm (segment tree, BFS, etc.)
   - Previous was sorting-based → try hash map, prefix sum, or monotonic stack
   - Previous was iterative → try recursive with memoization
4. Pay EXTREME attention to the I/O format — match it EXACTLY.
5. Handle ALL edge cases, especially the ones that caused the failure.

## {lang_name.upper()}-SPECIFIC RULES
- Keep the code concise (under ~60 lines).
- DO NOT use Python f-strings, triple quotes, or backticks. Use basic concatenation.
- Read from sys.stdin. Write to standard print.

## OUTPUT
Return ONLY the complete {lang_name} code using a DIFFERENT algorithmic approach. No explanations — just raw code."""

    try:
        logger.info(f"🔄 [CODE SOLVER]: Last resort — regenerating solution with a different approach using {CODING_MODEL}...")

        response = client.models.generate_content(
            model=CODING_MODEL,
            contents=prompt,
            config=_build_generate_config(),
        )

        raw_response = _get_response_text(response)

        if not raw_response:
            logger.error("❌ [CODE SOLVER]: Empty response on retry attempt")
            return previous_code

        code = _extract_code(raw_response, language)

        logger.info(f"🔄 [CODE SOLVER]: Generated alternative solution ({len(code)} chars, {code.count(chr(10)) + 1} lines)")
        return code

    except Exception as e:
        logger.error(f"❌ [CODE SOLVER]: Retry failed: {e}")
        return previous_code
