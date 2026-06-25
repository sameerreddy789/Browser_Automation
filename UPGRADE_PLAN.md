# 🚀 Browser Automation — Complete Upgrade Plan

> **Project:** MBU Examly Browser Automation Agent  
> **Repository:** https://github.com/sameerreddy789/Browser_Automation  
> **Date:** June 2026  
> **Status:** Plan — Not Yet Implemented  

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current Architecture Analysis](#2-current-architecture-analysis)
3. [Problems Identified](#3-problems-identified)
4. [Target Architecture](#4-target-architecture)
5. [Phase 1 — Remove Unnecessary Infrastructure](#5-phase-1--remove-unnecessary-infrastructure)
6. [Phase 2 — Upgrade the Coding Brain (code_solver.py)](#6-phase-2--upgrade-the-coding-brain-code_solverpy)
7. [Phase 3 — Rewrite the Examly System Prompt (main.py)](#7-phase-3--rewrite-the-examly-system-prompt-mainpy)
8. [Phase 4 — Terminal-Based AI Consultation Channel](#8-phase-4--terminal-based-ai-consultation-channel)
9. [Phase 5 — GSD-Inspired Context Engineering](#9-phase-5--gsd-inspired-context-engineering)
10. [Phase 6 — Clean Up & Simplify Remaining Files](#10-phase-6--clean-up--simplify-remaining-files)
11. [Phase 7 — Ensure MCQ Flow & Replay Stay Working](#11-phase-7--ensure-mcq-flow--replay-stay-working)
12. [File-by-File Change Summary](#12-file-by-file-change-summary)
13. [Dependency Changes (pyproject.toml)](#13-dependency-changes-pyprojecttoml)
14. [Testing Checklist](#14-testing-checklist)

---

## 1. Executive Summary

This plan covers a complete overhaul of the MBU Examly browser automation project. The goals are:

| Goal | Current State | Target State |
|------|--------------|--------------|
| **Coding speed** | ~30 min for 3 questions | ~5 min for 3 questions (solve once, verify, fix if needed, move on) |
| **Coding model** | `gemini-3.1-flash-lite` (weak) everywhere | `gemini-2.5-flash` for coding, `gemini-3.1-flash-lite` for navigation |
| **Architecture** | Redis + Taskiq + PocketBase + Streamlit + Mem0 + ChromaDB | Just the agent + answer bank + terminal AI consultation |
| **System prompt** | ~150 lines bloated monolith | Structured, modular, GSD-inspired prompts |
| **Agent↔Human communication** | PocketBase dashboard + Streamlit | Terminal-based: agent prints, AI model (via API) responds |
| **MCQ accuracy** | Good | Untouched — keep as-is |

### Guiding Principles

1. **Simplicity First** — Remove every service, library, and abstraction that doesn't directly contribute to "agent opens browser → solves test → finishes"
2. **Two-Brain Architecture** — Lightweight model for navigation (clicking, reading, scrolling), powerful model for coding (DSA reasoning)
3. **Solve Once, Verify, Fix or Move On** — Not "guess, guess, guess"
4. **Terminal Is The Interface** — No dashboards, no databases. The agent prints to terminal. If stuck, an AI model (via API) is consulted through the same terminal
5. **Spec-Driven Context Engineering** — Borrow from GSD: structured prompts that prevent context rot in long agent sessions

---

## 2. Current Architecture Analysis

### What Exists Now

```
┌─────────────────────────────────────────────────────────┐
│                    main.py (724 lines)                   │
│  - Controller with 15+ custom actions                   │
│  - Massive 150-line Examly system prompt                │
│  - Both LLMs use gemini-3.1-flash-lite                  │
│  - Imports: hitl, memory_manager, tasks, parsers        │
└──────────────┬──────────────────────┬───────────────────┘
               │                      │
    ┌──────────▼──────────┐  ┌───────▼────────┐
    │  code_solver.py     │  │  multi_run.py   │
    │  (383 lines)        │  │  (339 lines)    │
    │  Uses flash-lite!   │  │  Multi-account  │
    └──────────┬──────────┘  └───────┬────────┘
               │                     │
    ┌──────────▼──────────┐  ┌─────▼──────────┐
    │  replay_direct.py   │  │  answer_bank.py │
    │  (948 lines)        │  │  (207 lines)     │
    │  Pure Playwright    │  │  JSON-based      │
    └─────────────────────┘  └────────────────┘

    INFRASTRUCTURE (to be removed):
    ┌──────────────────────────────────────────┐
    │ tasks.py        - Taskiq Redis queue      │
    │ run.py          - PocketBase + Streamlit  │
    │ memory_manager.py - Mem0 + ChromaDB       │
    │ hitl/           - PocketBase client +     │
    │                   Streamlit dashboard      │
    │ session_store.py - Redis + local JSON     │
    └──────────────────────────────────────────┘

    KEEP AS-IS:
    ┌──────────────────────────────────────────┐
    │ stealth.py       - Anti-bot (playwright-stealth, etc.) │
    │ visual_grounding.py - Gemini vision fallback           │
    │ proxy/           - Proxy rotation                      │
    │ parsers/crawlee_parser.py - Crawlee extraction         │
    └──────────────────────────────────────────┘
```

### Key File Sizes

| File | Lines | Role |
|------|-------|------|
| main.py | 724 | Core agent, controller, system prompt |
| code_solver.py | 383 | DSA coding solver (3 functions: solve, fix, retry) |
| multi_run.py | 339 | Multi-account orchestrator |
| replay_direct.py | 948 | Zero-API pure Playwright replay |
| session_store.py | 271 | Session persistence (Redis + local JSON) |
| answer_bank.py | 207 | Q&A storage with Jaccard similarity |
| visual_grounding.py | 264 | Gemini vision fallback |
| stealth.py | 144 | Anti-bot protections |
| memory_manager.py | 60 | Mem0 + ChromaDB (REMOVE) |
| tasks.py | 51 | Taskiq worker (REMOVE) |
| run.py | 161 | PocketBase + Streamlit launcher (REMOVE) |

---

## 3. Problems Identified

### Problem 1: Wrong Model for Coding
**Severity: CRITICAL**

The `code_solver.py` docstring says it uses `gemini-2.5-flash (full thinking model)` but **ALL actual API calls use `gemini-3.1-flash-lite`**:

- Line 202: `model="gemini-3.1-flash-lite"` (solve_problem)
- Line 286: `model="gemini-3.1-flash-lite"` (fix_solution)  
- Line 366: `model="gemini-3.1-flash-lite"` (solve_problem_retry)

This is the #1 reason coding is slow and bad. The lite model cannot do deep algorithmic reasoning.

### Problem 2: Same Weak Model for Navigation LLM
**Severity: HIGH**

Both primary and fallback LLMs in `main.py` lines 623-634 use `gemini-3.1-flash-lite`. This is fine for navigation (clicking buttons, reading pages) but there's no distinction. The fallback should use a different model for resilience.

### Problem 3: Bloated System Prompt (~150 lines)
**Severity: HIGH**

The Examly system prompt in `main.py` (lines 472-620) is a monolithic wall of text covering:
- Navigation instructions
- Coding workflow (repeated 3 times in different sections)
- Self-healing protocols
- Monaco editor injection instructions
- Modal dismissal
- Visual grounding
- HITL escalation
- Answer bank usage

This causes **context rot** — the agent loses focus on what it should be doing right now.

### Problem 4: Unnecessary Infrastructure
**Severity: MEDIUM**

Redis, Taskiq, PocketBase, Streamlit, Mem0, ChromaDB add:
- Startup dependencies (Redis must be running)
- Failure points (connection refused, timeouts)
- Complexity (multiple services to manage)
- Zero value for single-machine automated runs

### Problem 5: HITL via Dashboard is Overkill
**Severity: MEDIUM**

The PocketBase + Streamlit HITL system (`hitl/` directory) requires:
- PocketBase server running
- Streamlit dashboard running
- A browser tab to view the dashboard

For a terminal-based automation tool, the agent should just print to terminal and read from terminal. If an AI model needs to help, it should be via API — not a web dashboard.

### Problem 6: No Programmatic Verification Loop
**Severity: HIGH**

The current workflow is:
1. Agent calls `solve_coding_question` → gets code
2. Agent injects code → clicks Compile & Run
3. Agent reads results (sometimes)
4. If failing, agent calls `fix_coding_solution`
5. Repeat

But the agent is a BROWSER agent — it's not great at reading test output panels. The verification should be more structured and the "move on after 3 attempts" rule should be enforced programmatically, not just mentioned in the prompt.

---

## 4. Target Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                        main.py (simplified)                   │
│  - Concise system prompt (~60 lines, modular)                │
│  - Controller with focused actions                            │
│  - Navigation LLM: gemini-3.1-flash-lite                      │
│  - Fallback LLM: gemini-2.5-flash (stronger, for resilience) │
└────────────┬──────────────────────────┬──────────────────────┘
             │                          │
  ┌──────────▼───────────┐   ┌─────────▼──────────┐
  │  code_solver.py      │   │  ai_consultant.py  │
  │  (upgraded)          │   │  (NEW)             │
  │  Model: gemini-2.5- │   │  Gemini API →      │
  │  flash with thinking│   │  terminal I/O      │
  └──────────┬───────────┘   └────────────────────┘
             │
  ┌──────────▼───────────┐   ┌─────────┐
  │  replay_direct.py    │   │ answer   │
  │  (untouched)         │   │ _bank.py │
  └───────────────────────┘   └─────────┘

  SUPPORTING (kept as-is):
  - stealth.py, visual_grounding.py, proxy/, parsers/
  
  REMOVED:
  - tasks.py, run.py, memory_manager.py, hitl/
  - Redis, Taskiq, PocketBase, Streamlit, Mem0, ChromaDB deps
  
  SIMPLIFIED:
  - session_store.py → local JSON only (remove Redis)
```

### The Two-Brain Model

| Brain | Model | Purpose | When |
|-------|-------|---------|------|
| **Navigation** | `gemini-3.1-flash-lite` | Click, read, navigate, decide | Every agent step |
| **Coding** | `gemini-2.5-flash` | Solve DSA problems with deep reasoning | `solve_coding_question`, `fix_coding_solution`, `retry_coding_solution` |
| **AI Consultant** | `gemini-2.5-flash` | Answer complex questions from terminal | When agent escalates via `request_user_input` |

---

## 5. Phase 1 — Remove Unnecessary Infrastructure

### 5.1 Delete Files

Delete these files entirely:

| File | Reason |
|------|--------|
| `tasks.py` | Taskiq Redis queue worker — not needed for single-machine runs |
| `run.py` | PocketBase + Streamlit launcher — replaced by terminal I/O |
| `memory_manager.py` | Mem0 + ChromaDB memory — not needed |
| `hitl/__init__.py` | HITL client — replaced by terminal consultation |
| `hitl/dashboard.py` | Streamlit dashboard — replaced by terminal |
| `hitl/pocketbase_client.py` | PocketBase client — not needed |
| `hitl/setup_pocketbase.py` | PocketBase setup — not needed |

Commands:
```bash
rm tasks.py run.py memory_manager.py
rm -rf hitl/
```

### 5.2 Remove Imports in main.py

In `main.py`, remove these imports (currently at lines 20-22):
```python
# REMOVE these lines:
from hitl import HITLClient
from memory_manager import memory_manager
from parsers.crawlee_parser import extract_page_data_crawlee  # keep if used elsewhere
```

Also remove all references to `_hitl_client` throughout the file:
- Line 671: `global _hitl_client`
- Line 672: `_hitl_client = HITLClient()`
- Line 673: `_hitl_client.update_state("RUNNING", ...)`
- Lines 711, 714: `_hitl_client.update_state("COMPLETED", ...)`

Remove the Taskiq queue code block (lines 693-701):
```python
# REMOVE this entire block:
if args.queue:
    from tasks import broker, run_browser_agent_task
    ...
```

Remove the `--queue` argument from argparse.

### 5.3 Clean Up pyproject.toml

Remove these dependencies:
```toml
# REMOVE:
"pocketbase>=0.17.0",
"streamlit>=1.35.0",
"redis>=5.0.4",
"mem0ai>=2.0.4",
"taskiq>=0.12.4",
"taskiq-redis>=1.2.2",
"chromadb>=1.5.9",
"mitmproxy>=12.2.3",
```

Keep these:
```toml
# KEEP:
"browser-use>=0.12.9",
"langchain-google-genai>=4.2.4",
"playwright>=1.60.0",
"python-dotenv>=1.2.2",
"python-ghost-cursor>=0.1.1",
"playwright-stealth>=1.0.6",
"curl-cffi>=0.7.4",
"loguru>=0.7.3",
"crawlee[playwright]>=1.7.2",
```

### 5.4 Clean .env.example

Remove these variables:
```
REDIS_HOST=
REDIS_PORT=
POCKETBASE_URL=
MEM0_API_KEY=
```

Keep:
```
GEMINI_API_KEY=
```

### 5.5 Simplify session_store.py

Remove the Redis import and all Redis-related code. Keep ONLY the local JSON file fallback. The file goes from ~270 lines to ~100 lines.

Key changes:
- Remove `import redis` and Redis connection setup
- Remove the `RedisSessionStore` class entirely
- Keep only `LocalSessionStore` (JSON-based)
- Simplify the `SessionStore` factory to just return `LocalSessionStore`

---

## 6. Phase 2 — Upgrade the Coding Brain (code_solver.py)

### 6.1 Change the Model

**Before:**
```python
model="gemini-3.1-flash-lite",  # Lines 202, 286, 366
```

**After:**
```python
model="gemini-2.5-flash",  # All three functions
```

### 6.2 Enable Thinking Mode

`gemini-2.5-flash` supports thinking/reasoning. Enable it for deeper analysis:

```python
from google.genai import ThinkingConfig

thinking_config = ThinkingConfig(
    include_thoughts=True,  # Include thinking traces in response
)

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt,
    config={
        "thinking_config": thinking_config,
        "temperature": 0.2,  # Low temp for consistent, precise solutions
    },
)
```

### 6.3 Improve the solve_problem() Prompt

The current prompt is decent but has issues:
- Says "under 50 lines" which is too restrictive for complex DSA
- Doesn't emphasize time/space complexity explicitly enough
- Has C++-specific notes mixed with Python

**New prompt structure:**

```python
prompt = f"""You are an expert competitive programmer solving a DSA problem.

## PROBLEM
{problem_statement}

## REQUIREMENTS
- Language: {lang_name}
- Optimize for time AND space complexity
- Read input from sys.stdin, write to stdout
- Output EXACTLY what the problem specifies — no extra text

## CONSTRAINTS CHECK
Before coding, state the problem constraints and determine the minimum time complexity needed:
- n ≤ 10^5 → need O(n log n) or better
- n ≤ 10^6 → need O(n) or O(n log n)  
- k ≤ 10^5 with n ≤ 10^5 → need O(n log n) or sliding window
- Multiple test cases → amortized per-case cost must be efficient

## PYTHON-SPECIFIC RULES
- DO NOT use f-strings (causes injection errors in Monaco editor)
- Use str() + concatenation or .format() instead
- DO NOT use triple quotes or backticks in code
- Keep code clean and readable

## OUTPUT
Return ONLY the {lang_name} code. No explanations, no markdown fences, no comments about approach.
Just the raw code ready to compile and run."""
```

### 6.4 Improve the fix_solution() Prompt

Add structured failure analysis:

```python
prompt = f"""You are debugging a failing DSA solution. Analyze the failure and fix it.

## PROBLEM
{problem_statement}

## CURRENT CODE (FAILING)
{current_code}

## FAILURE DETAILS
{failure_details}

## SYSTEMATIC DEBUG CHECKLIST
1. **I/O Format**: Does output match exactly? Check spaces, newlines, trailing whitespace
2. **Edge Cases**: n=0, n=1, negative numbers, empty strings, single element
3. **Integer Overflow**: Python handles big ints, but check for logic errors
4. **Off-by-One**: Loop bounds, array indexing (0-based vs 1-based)
5. **Wrong Algorithm**: Is the fundamental approach wrong? (e.g., greedy when DP needed)
6. **Time Limit**: If TLE, need fundamentally different approach

## INSTRUCTIONS
- If small bug (format, edge case): Make targeted fix
- If algorithm is fundamentally wrong: Rewrite with correct approach
- Verify your fix mentally against the failing test case
- Ensure fix doesn't break other passing test cases

## OUTPUT
Return ONLY the fixed {lang_name} code."""
```

### 6.5 Improve the retry_coding_solution() Prompt

Make it more explicit about trying different algorithmic paradigms:

```python
prompt = f"""Previous attempts failed. Solve with a COMPLETELY DIFFERENT approach.

## PROBLEM
{problem_statement}

## PREVIOUS FAILED CODE
{previous_code}

## WHY IT FAILED
{all_failure_details}

## ALTERNATIVE STRATEGIES
- If greedy failed → try DP, binary search, or two-pointer
- If DP failed → try greedy with proof, or different state definition
- If brute force → use optimal algorithm (segment tree, BFS, etc.)
- If sorting-based failed → try hash map, prefix sum, or monotonic stack
- If iterative failed → try recursive with memoization

## OUTPUT
Return ONLY the {lang_name} code using a different algorithmic approach."""
```

### 6.6 Add Configurable Model via Environment Variable

Allow overriding the coding model via `.env`:

```python
import os
CODING_MODEL = os.getenv("CODING_MODEL", "gemini-2.5-flash")
```

This way, if `gemini-2.5-flash` has issues, you can switch to `gemini-2.5-pro` or another model without code changes.

---

## 7. Phase 3 — Rewrite the Examly System Prompt (main.py)

### 7.1 The Problem

The current prompt is ~150 lines of repetitive, interleaved instructions. The agent has to hold ALL of this in context at every step, leading to:
- Forgetting critical rules (like "don't open new tabs")
- Repeating the coding workflow explanation 3 times
- Mixing navigation instructions with troubleshooting

### 7.2 GSD-Inspired Approach

Borrow from get-shit-done's context engineering:
1. **Modular prompts** — Break into focused sections that are loaded contextually
2. **Spec-driven** — Each section has a clear purpose
3. **Progressive disclosure** — Only show what's relevant to the current phase
4. **State tracking** — Help the agent know what phase it's in

### 7.3 New Prompt Structure

Replace the monolithic prompt with a **concise base + modular injections**:

```python
# Base prompt — always loaded (~40 lines)
task_instructions = f"""
You are ExamlyBot, an automated test-taking assistant for the MBU Examly platform.

## MISSION
Complete the assessment: '{task_goal}'
URL: {target_url}
Account: {email} / {password}

## ABSOLUTE RULES
- NEVER open new tabs or switch tabs. Tab switching = auto-submit = FAIL
- NEVER Google search or use any external resource
- Work ONLY within the primary browser tab

## WORKFLOW
1. Login → 2. Navigate to course/assessment → 3. Answer questions → 4. Submit
4. For MCQs: Read question → Select correct answer → Next
5. For Coding: Use the 3-tier solver (solve → verify → fix if needed → move on after 3 tries)

## CURRENT MODE: {run_mode.upper()}
{replay_mode_note if run_mode == 'replay' else ''}

{memory_note if agent_memory_content else ''}
"""
```

### 7.4 Modular Prompt Components

Create a `prompts/` directory with focused prompt files:

```
prompts/
├── __init__.py
├── examly_login.py      # Login flow instructions
├── examly_navigation.py # Course/assessment navigation
├── examly_mcq.py        # MCQ answering strategy
├── examly_coding.py     # Coding question workflow (detailed)
├── examly_submit.py     # Final submission + END typing
├── troubleshooting.py   # Modal dismissal, button enabling, etc.
└── visual_fallback.py   # Visual grounding instructions
```

These are NOT loaded all at once. Instead, the base prompt references them, and the agent's action descriptions provide contextual detail.

### 7.5 Key Changes to the Examly Prompt

| Before | After |
|--------|-------|
| 150-line monolith | ~40-line base + focused action descriptions |
| Coding workflow repeated 3x | Explained once in `examly_coding.py` module |
| "Use gemini-2.5-flash" (lie) | Just says "Use the dedicated coding solver" |
| HITL escalation → PocketBase dashboard | HITL escalation → terminal AI consultant |
| Self-healing mixed in | Separated into `troubleshooting.py` |

### 7.6 The Login Flow (examly_login.py)

```python
LOGIN_PROMPT = """
## LOGIN FLOW
1. Navigate to {target_url}
2. If already logged in as wrong user → Logout first (top-right dropdown)
3. Enter email '{email}' → Click 'Next'
4. Enter password '{password}' → Click 'Login'
5. Wait for dashboard to load
"""
```

### 7.7 The Coding Workflow (examly_coding.py)

This is the most critical module. It should be clear, structured, and leave no ambiguity:

```python
CODING_WORKFLOW = """
## CODING QUESTION WORKFLOW
When you encounter a coding question, follow this EXACT sequence:

### Step 1: Understand
- Read the ENTIRE problem: title, description, examples, constraints, I/O format
- Note the time/space constraints — they determine the required algorithm complexity

### Step 2: Solve
- Call `solve_coding_question` with the COMPLETE problem text
- The solver returns optimal code (it uses a powerful reasoning model)
- Default language: Python 3

### Step 3: Inject
- Ensure language dropdown is set to Python 3
- Call `inject_code_to_editor` with the returned code
- NEVER type code manually or use keyboard input for code

### Step 4: Verify
- Click 'Compile & Run'
- Read ALL test case results from the output panel
- If ALL pass → Click 'Submit Code' → Done, move to next question

### Step 5: Fix (if failing)
- Read the EXACT expected vs actual output for each failing test case
- Call `fix_coding_solution` with: problem, current code, failure details
- Inject fixed code → Compile & Run again

### Step 6: Retry (if still failing)
- Call `retry_coding_solution` with: problem, failing code, ALL accumulated failures
- This tries a completely different algorithm
- Inject → Compile & Run

### Step 7: Move On (HARD LIMIT)
- MAXIMUM 3 attempts (1 solve + 1 fix + 1 retry)
- After 3rd attempt fails → Submit best attempt immediately
- DO NOT try a 4th time. Time is critical.
"""
```

### 7.8 Updated Model Setup

```python
# Navigation brain — lightweight, fast
llm = ChatGoogle(
    model="gemini-3.1-flash-lite",
    max_retries=5,
    retry_base_delay=3.0,
    retry_max_delay=30.0,
)

# Fallback brain — stronger, for when lite fails
fallback_llm = ChatGoogle(
    model="gemini-2.5-flash",  # Upgraded from flash-lite
    max_retries=5,
    retry_base_delay=5.0,
    retry_max_delay=60.0,
)
```

---

## 8. Phase 4 — Terminal-Based AI Consultation Channel

### 8.1 Concept

Replace the PocketBase + Streamlit HITL system with a simple terminal-based AI consultation:

1. **Agent encounters blocker** → Calls `request_ai_help` action
2. **Terminal prints the question** → User (or AI via API) types a response
3. **Agent receives the answer** → Continues its work

This is the `request_user_input` action that ALREADY EXISTS (main.py lines 36-43)! We just need to:
- Make it more prominent
- Add an optional `ai_consultant.py` that can auto-answer via Gemini API
- Let the user choose: manual terminal input OR AI auto-answer

### 8.2 New File: ai_consultant.py

```python
"""
ai_consultant.py — AI-powered terminal consultant

When the browser agent encounters a blocker it can't solve on its own,
it can consult an AI model (via Gemini API) for help. This replaces
the old PocketBase/Streamlit HITL system.

Usage:
    from ai_consultant import consult_ai
    answer = await consult_ai("How do I handle this CAPTCHA?")
"""

import os
from google import genai
from loguru import logger

CONSULTANT_MODEL = os.getenv("CONSULTANT_MODEL", "gemini-2.5-flash")


async def consult_ai(question: str, context: str = "") -> str:
    """
    Ask the AI consultant a question.
    
    Args:
        question: The question from the browser agent
        context: Optional context (screenshot description, page state, etc.)
    
    Returns:
        The AI's answer
    """
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    
    system_prompt = """You are an AI assistant helping a browser automation agent. 
The agent is taking a test on the MBU Examly platform and has encountered a blocker.
Provide a concise, actionable answer. If the question is about:
- A CAPTCHA: Describe what you see in the image
- A page layout issue: Suggest CSS selectors or actions
- A coding problem: Provide the solution approach
- A login/auth issue: Suggest specific steps

Keep your answer under 3 sentences unless code is needed."""
    
    prompt = f"{system_prompt}\n\nQuestion: {question}"
    if context:
        prompt += f"\nContext: {context}"
    
    try:
        response = client.models.generate_content(
            model=CONSULTANT_MODEL,
            contents=prompt,
        )
        answer = response.text.strip()
        logger.info(f"🤖 [AI CONSULTANT]: {answer[:100]}...")
        return answer
    except Exception as e:
        logger.error(f"❌ [AI CONSULTANT]: Failed: {e}")
        return f"AI consultant error: {e}"


async def consult_ai_with_vision(question: str, image_path: str) -> str:
    """
    Ask the AI consultant with a screenshot for visual context.
    """
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    
    try:
        with open(image_path, "rb") as f:
            image_data = f.read()
        
        response = client.models.generate_content(
            model=CONSULTANT_MODEL,
            contents=[
                {"role": "user", "parts": [
                    {"text": f"You are helping a browser agent. {question}"},
                    {"inline_data": {"mime_type": "image/png", "data": image_data}},
                ]}
            ],
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"❌ [AI CONSULTANT]: Vision query failed: {e}")
        return ""
```

### 8.3 Enhanced request_user_input Action

Update the existing action to support both manual and AI consultation:

```python
@controller.action(
    description="Ask for help when stuck. The question will be printed to the terminal. "
                "A human or AI can respond to help unblock the agent. "
                "Use this as a last resort after trying self-healing and visual grounding."
)
async def request_user_input(question_prompt: str) -> str:
    """
    Terminal-based consultation:
    1. Print the question to terminal
    2. Wait for human input (or AI auto-answer if enabled)
    3. Return the response to the agent
    """
    print(f"\n\033[93m{'='*60}")
    print(f"[AGENT NEEDS HELP]: {question_prompt}")
    print(f"{'='*60}\033[0m")
    print("Type your answer, or 'ai' to let the AI consultant answer:")
    
    response = await asyncio.to_thread(sync_get_user_input, question_prompt)
    
    # If user types 'ai', auto-consult the AI
    if response.lower() == "ai":
        from ai_consultant import consult_ai
        answer = await consult_ai(question_prompt)
        print(f"\033[92m[AI CONSULTANT]: {answer}\033[0m")
        return answer
    
    return response
```

### 8.4 Remove Old HITL Actions

Remove any `pause_for_human_help` action that references PocketBase/dashboard. Replace with `request_user_input`.

---

## 9. Phase 5 — GSD-Inspired Context Engineering

### 9.1 What We're Borrowing from GSD

The [get-shit-done](https://github.com/gsd-build/get-shit-done) project teaches:

1. **Meta-prompting** — Prompts that generate other prompts (structured, not ad-hoc)
2. **Spec-driven workflows** — Define specs before implementation
3. **Context engineering** — Manage what context the LLM sees at each step to prevent rot
4. **Modular prompt architecture** — Small, focused prompts > one massive prompt

### 9.2 Implementation: prompts/ Directory

Create `prompts/__init__.py`:

```python
"""
Modular prompt system inspired by GSD context engineering.

Each prompt module is focused on ONE concern. The base agent prompt is kept short.
Detailed instructions are in action descriptions, not the main prompt.
"""

from prompts.examly_base import build_examly_prompt
from prompts.examly_coding import CODING_WORKFLOW
from prompts.examly_mcq import MCQ_STRATEGY
from prompts.examly_submit import SUBMISSION_GATE

__all__ = [
    "build_examly_prompt",
    "CODING_WORKFLOW", 
    "MCQ_STRATEGY",
    "SUBMISSION_GATE",
]
```

### 9.3 Prompt Injection Pattern

Instead of loading everything into the system prompt, inject context via action descriptions:

```python
@controller.action(
    description="Solves a DSA/coding question using a powerful reasoning model. "
                "This uses a separate, much stronger AI model optimized for algorithmic problems. "
                "Pass the COMPLETE problem text including examples, constraints, and I/O format."
)
async def solve_coding_question(question_text: str, language: str = "python") -> str:
    ...
```

The action description itself teaches the agent HOW to use it. This is more effective than repeating instructions in the system prompt.

### 9.4 Context Window Management

Keep the base system prompt under 50 lines. Everything else goes into:
- Action descriptions (seen when the agent considers actions)
- Modular prompt files (can be referenced by name if needed)
- Runtime context (only inject what's relevant to the current step)

---

## 10. Phase 6 — Clean Up & Simplify Remaining Files

### 10.1 session_store.py → Local Only

Remove all Redis code. Keep only the JSON file storage:

```python
"""session_store.py — Local JSON session storage."""

import json
import os
from pathlib import Path
from loguru import logger

SESSIONS_DIR = Path("sessions")


class LocalSessionStore:
    """Stores browser sessions as local JSON files."""
    
    def __init__(self):
        SESSIONS_DIR.mkdir(exist_ok=True)
    
    def save(self, session_id: str, data: dict) -> None:
        path = SESSIONS_DIR / f"{session_id}.json"
        path.write_text(json.dumps(data, indent=2))
    
    def load(self, session_id: str) -> dict | None:
        path = SESSIONS_DIR / f"{session_id}.json"
        if path.exists():
            return json.loads(path.read_text())
        return None
    
    def list_sessions(self) -> list[str]:
        return [p.stem for p in SESSIONS_DIR.glob("*.json")]
    
    def delete(self, session_id: str) -> None:
        path = SESSIONS_DIR / f"{session_id}.json"
        if path.exists():
            path.unlink()


# Single instance
session_store = LocalSessionStore()
```

### 10.2 Update .gitignore

Add to `.gitignore`:
```
# Debug screenshots
debug_*.png

# AI consultant logs
consultant_*.log
```

### 10.3 Clean main.py Imports

Final import list for main.py:
```python
import os
import asyncio
import argparse

from dotenv import load_dotenv
from browser_use import Agent, ChatGoogle, Controller
from browser_use.browser.session import BrowserSession
from browser_use.browser.profile import BrowserProfile
from google import genai
from PIL import Image
from python_ghost_cursor.playwright_async import create_cursor

from stealth import get_stealth_browser_args
from visual_grounding import (
    click_element_visually, find_element_coordinates, 
    visual_scroll_to, describe_page_visually
)
from proxy import ProxyRotator
from loguru import logger
```

Removed imports:
- `from hitl import HITLClient`
- `from memory_manager import memory_manager`

### 10.4 Update .env.example

```env
# === REQUIRED ===
GEMINI_API_KEY=your_gemini_api_key_here

# === OPTIONAL: Override default models ===
# NAVIGATION_MODEL=gemini-3.1-flash-lite
# CODING_MODEL=gemini-2.5-flash
# CONSULTANT_MODEL=gemini-2.5-flash

# === OPTIONAL: Proxy ===
# PROXY_HOST=
# PROXY_PORT=
# PROXY_USERNAME=
# PROXY_PASSWORD=
```

---

## 11. Phase 7 — Ensure MCQ Flow & Replay Stay Working

### 11.1 MCQ Flow

The MCQ answering flow is currently working well. Changes that could affect it:
- **System prompt rewrite** — Must keep the MCQ instructions intact (just restructured)
- **Model change** — Navigation model stays `gemini-3.1-flash-lite` (no change)
- **Removed imports** — HITL/memory_manager removal doesn't affect MCQ answering

**Verification:** After implementation, run the agent on an MCQ-only test to confirm.

### 11.2 replay_direct.py

This is a standalone 948-line Playwright script that doesn't import from main.py. Changes:
- **No direct impact** — It imports from `answer_bank.py` only
- **session_store.py changes** — replay_direct.py doesn't use session_store
- **Code solver changes** — replay_direct.py doesn't use code_solver.py (it replays saved answers)

**Verification:** Confirm `answer_bank.py` is not modified in ways that break the replay.

### 11.3 answer_bank.py

No changes needed. The answer bank works well and is not dependent on any removed infrastructure.

### 11.4 multi_run.py

Review for any imports from removed modules. It imports from:
- `answer_bank` — Keep
- `main` (for task setup) — Update if main.py's interface changes
- Standard library — Keep

If multi_run.py imports `tasks` or `hitl`, remove those references.

---

## 12. File-by-File Change Summary

| File | Action | What Changes |
|------|--------|-------------|
| `main.py` | **MODIFY** | Remove HITL/memory_manager imports; shorten system prompt; upgrade fallback model; remove Taskiq queue code; enhance `request_user_input` |
| `code_solver.py` | **MODIFY** | Change model to `gemini-2.5-flash`; enable thinking config; improve prompts; add env-configurable model |
| `multi_run.py` | **MODIFY** | Remove any imports from deleted modules; minor cleanup |
| `session_store.py` | **SIMPLIFY** | Remove Redis; keep only local JSON storage |
| `answer_bank.py` | **NO CHANGE** | Working well, leave untouched |
| `replay_direct.py` | **NO CHANGE** | Standalone, no dependencies on removed modules |
| `visual_grounding.py` | **NO CHANGE** | Keep as-is |
| `stealth.py` | **NO CHANGE** | Keep as-is |
| `proxy/` | **NO CHANGE** | Keep as-is |
| `parsers/` | **NO CHANGE** | Keep as-is |
| `ai_consultant.py` | **CREATE** | New file — AI-powered terminal consultation |
| `prompts/__init__.py` | **CREATE** | Modular prompt system |
| `prompts/examly_base.py` | **CREATE** | Base Examly prompt builder |
| `prompts/examly_coding.py` | **CREATE** | Coding workflow prompt module |
| `prompts/examly_mcq.py` | **CREATE** | MCQ strategy prompt module |
| `prompts/examly_submit.py` | **CREATE** | Submission gate prompt module |
| `prompts/troubleshooting.py` | **CREATE** | Self-healing prompt module |
| `tasks.py` | **DELETE** | Taskiq worker — removed |
| `run.py` | **DELETE** | PocketBase + Streamlit launcher — removed |
| `memory_manager.py` | **DELETE** | Mem0 + ChromaDB — removed |
| `hitl/` | **DELETE (dir)** | PocketBase client + Streamlit dashboard — removed |
| `pyproject.toml` | **MODIFY** | Remove pocketbase, streamlit, redis, mem0, taskiq, taskiq-redis, chromadb, mitmproxy deps |
| `.env.example` | **MODIFY** | Remove Redis/PocketBase/Mem0 vars; add model override vars |
| `.gitignore` | **MODIFY** | Add debug screenshots and consultant logs |

---

## 13. Dependency Changes (pyproject.toml)

### Removed Dependencies

| Package | Why |
|---------|-----|
| `pocketbase>=0.17.0` | No PocketBase server needed |
| `streamlit>=1.35.0` | No web dashboard needed |
| `redis>=5.0.4` | No Redis server needed |
| `mem0ai>=2.0.4` | No AI memory DB needed |
| `taskiq>=0.12.4` | No task queue needed |
| `taskiq-redis>=1.2.2` | No Redis queue needed |
| `chromadb>=1.5.9` | No vector DB needed |
| `mitmproxy>=12.2.3` | Proxy addon uses it but can be optional |

### Kept Dependencies

| Package | Why |
|---------|-----|
| `browser-use>=0.12.9` | Core agent framework |
| `langchain-google-genai>=4.2.4` | LLM integration |
| `playwright>=1.60.0` | Browser automation |
| `python-dotenv>=1.2.2` | Environment variables |
| `python-ghost-cursor>=0.1.1` | Anti-detection cursor |
| `playwright-stealth>=1.0.6` | Anti-bot |
| `curl-cffi>=0.7.4` | TLS fingerprinting |
| `loguru>=0.7.3` | Logging |
| `crawlee[playwright]>=1.7.2` | Page data extraction |

---

## 14. Testing Checklist

After implementation, verify:

- [ ] **Agent starts without errors** — `python main.py --url ... --email ... --password ...`
- [ ] **No Redis/Taskiq/PocketBase/Streamlit errors** — All references removed
- [ ] **Login works** — Can log into Examly platform
- [ ] **Navigation works** — Can find course and assessment
- [ ] **MCQ answering works** — Can select answers correctly
- [ ] **Coding solver uses gemini-2.5-flash** — Check logs for model name
- [ ] **Coding solutions are generated faster** — Should see significant speedup
- [ ] **3-try limit is enforced** — Agent moves on after 3 attempts
- [ ] **Terminal AI consultation works** — Type 'ai' to get AI help
- [ ] **replay_direct.py still works** — Zero-API replay unaffected
- [ ] **Answer bank saves/loads correctly** — JSON operations intact
- [ ] **No import errors** — `python -c "import main"` works
- [ ] **uv sync** — Dependencies install cleanly

---

## Implementation Order

1. **Phase 1** — Delete files and remove infrastructure (safest, lowest risk)
2. **Phase 6** — Clean up remaining files (session_store, .env, .gitignore)
3. **Phase 2** — Upgrade code_solver.py (highest impact on coding speed)
4. **Phase 4** — Create ai_consultant.py and enhance terminal consultation
5. **Phase 5** — Create prompts/ directory with modular prompts
6. **Phase 3** — Rewrite main.py system prompt using new modular prompts
7. **Phase 7** — Verify MCQ and replay still work

---

*This plan was written on June 25, 2026. Implementation follows immediately after push to GitHub.*
