import os
import asyncio
import argparse
import re
import io

from dotenv import load_dotenv
from browser_use import Agent, ChatGoogle, Controller
from browser_use.browser.session import BrowserSession
from browser_use.browser.profile import BrowserProfile
from google import genai
from PIL import Image
from python_ghost_cursor.playwright_async import create_cursor

# New architecture modules
from stealth import get_stealth_browser_args
from visual_grounding import click_element_visually, find_element_coordinates, visual_scroll_to, describe_page_visually

from proxy import ProxyRotator
from parsers.crawlee_parser import extract_page_data_crawlee

# Set up logging configuration
from loguru import logger


# Initialize Controller for custom actions
controller = Controller()

# Helper for synchronous blocking input in worker thread
def sync_get_user_input(prompt: str) -> str:
    print(f"\n\033[93m[AGENT NEEDS HELP]: {prompt}\033[0m")
    print("\033[90m(Type your answer, or 'ai' to let the AI consultant auto-answer)\033[0m")
    return input(">> Your Response: ").strip()

@controller.action(
    description="Ask for help when stuck. Prints the question to the terminal and waits for a response. "
                "A human can type an answer, OR type 'ai' to let an AI consultant (via API) answer automatically. "
                "Use this when you hit ambiguity, an unknown blocker, or need a decision you cannot confidently make."
)
async def request_user_input(question_prompt: str) -> str:
    response = await asyncio.to_thread(sync_get_user_input, question_prompt)
    # If user delegates to AI, consult the AI consultant via API
    if response.lower() == "ai":
        try:
            from ai_consultant import consult_ai
            answer = await consult_ai(question_prompt)
            print(f"\033[92m[AI CONSULTANT]: {answer}\033[0m")
            return answer
        except Exception as e:
            logger.error(f"AI consultant failed: {e}")
            return f"AI consultant unavailable ({e}). Continuing with best effort."
    return response

@controller.action(
    description="Saves a lesson learned, site-specific fix, or error-recovery workaround for future runs. "
                "Use this when you successfully bypass a bug, enable a disabled button, close a blocking overlay, "
                "or interact with a complex editor using custom JS."
)
def save_agent_knowledge(site_name: str, error_description: str, solution_javascript: str) -> str:
    import json
    from pathlib import Path
    knowledge_dir = Path("agent_profile") / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    knowledge_file = knowledge_dir / f"{site_name}.json"
    entries = []
    if knowledge_file.exists():
        entries = json.loads(knowledge_file.read_text())
    entries.append({"error": error_description, "fix_js": solution_javascript})
    knowledge_file.write_text(json.dumps(entries, indent=2))
    return f"Successfully saved knowledge for {site_name}. It will be loaded automatically on next run."

@controller.action(
    description="Solves a text-based image CAPTCHA on the current webpage by screenshotting the image element and using Gemini AI."
)
async def solve_captcha_image(image_selector: str, browser_session: BrowserSession) -> str:
    try:
        page = await browser_session.get_current_page()
        elements = await page.get_elements_by_css_selector(image_selector)
        if not elements:
            return f"Error: CAPTCHA image element with selector '{image_selector}' not found."
        element = elements[0]
            
        screenshot_bytes = await element.screenshot()
        image = Image.open(io.BytesIO(screenshot_bytes))
        
        client = genai.Client()
        response = client.models.generate_content(
            model='gemini-2.5-flash',  # Use gemini-2.5-flash since 3.1-flash-lite quota is exhausted
            contents=[
                image,
                "Identify the alphanumeric characters in this CAPTCHA image. "
                "Reply ONLY with the solved characters. Do not include spaces, "
                "punctuation, or any introductory/explanatory text. If there are Persian/Farsi digits, "
                "convert them to standard English digits. If no characters are clear, return an empty response."
            ]
        )
        
        solution = response.text.strip().replace(" ", "")
        logger.info(f"🤖 [CAPTCHA SOLVER]: Solved CAPTCHA as '{solution}'")
        return solution
    except Exception as e:
        logger.error(f"Error solving captcha: {e}")
        return f"Error: Failed to solve CAPTCHA due to: {str(e)}"

@controller.action(
    description="Clicks on an element using a human-like curved mouse path (ghost cursor) to bypass anti-bot systems."
)
async def human_click(selector: str, browser_session: BrowserSession) -> str:
    try:
        page = await browser_session.get_current_page()
        elements = await page.get_elements_by_css_selector(selector)
        if not elements:
            return f"Error: Element with selector '{selector}' not found."
        element = elements[0]
            
        await element.click()
        return f"Successfully clicked element '{selector}' using CDP click."
        logger.info(f"🖱️ [GHOST CURSOR]: Human-like click on '{selector}' completed.")
        return f"Successfully clicked element '{selector}' using human-like cursor movements."
    except Exception as e:
        logger.error(f"Error in human_click: {e}")
        return f"Error: Human-like click failed: {str(e)}"

@controller.action(
    description="Hovers over an element using a human-like curved mouse path (ghost cursor) to trigger hover behaviors."
)
async def human_hover(selector: str, browser_session: BrowserSession) -> str:
    try:
        page = await browser_session.get_current_page()
        element = await page.query_selector(selector)
        if not element:
            return f"Error: Element with selector '{selector}' not found."
            
        cursor = await create_cursor(page)
        await cursor.move_to(element)
        logger.info(f"🖱️ [GHOST CURSOR]: Human-like hover on '{selector}' completed.")
        return f"Successfully hovered over element '{selector}' using human-like cursor movements."
    except Exception as e:
        logger.error(f"Error in human_hover: {e}")
        return f"Error: Human-like hover failed: {str(e)}"

# ── Visual Grounding Actions ──────────────────────────────────────────────────

@controller.action(
    description="Clicks an element by visually describing it (e.g., 'the blue Login button'). "
                "Uses AI vision to find the element on a screenshot and click its coordinates. "
                "Use this when CSS selectors fail or the page layout has changed unexpectedly."
)
async def visual_click(element_description: str, browser_session: BrowserSession) -> str:
    try:
        page = await browser_session.get_current_page()
        success = await click_element_visually(page, element_description)
        if success:
            return f"Successfully clicked '{element_description}' using visual grounding."
        else:
            return f"Could not find '{element_description}' on the page visually."
    except Exception as e:
        logger.error(f"Error in visual_click: {e}")
        return f"Error: Visual click failed: {str(e)}"

@controller.action(
    description="Finds the pixel coordinates of an element by describing what it looks like. "
                "Returns the x,y position without clicking. Useful for inspecting element positions."
)
async def visual_find(element_description: str, browser_session: BrowserSession) -> str:
    try:
        page = await browser_session.get_current_page()
        coords = await find_element_coordinates(page, element_description)
        if coords:
            return f"Found '{element_description}' at pixel coordinates ({coords[0]:.0f}, {coords[1]:.0f})."
        else:
            return f"Could not find '{element_description}' on the page."
    except Exception as e:
        logger.error(f"Error in visual_find: {e}")
        return f"Error: Visual find failed: {str(e)}"

@controller.action(
    description="Extracts all text data efficiently from a specific CSS selector using Crawlee. "
                "Use this when you need to read a lot of text or scrape a list without taking screenshots."
)
async def scrape_text_data(url: str, selector: str = "body") -> str:
    try:
        logger.info(f"🕸️ Extracting text from {url} using selector {selector}")
        data = await extract_page_data_crawlee(url, selector)
        return f"Extracted Data:\n{data[:2000]}...\n[Truncated if too long]"
    except Exception as e:
        logger.error(f"Error in scrape_text_data: {e}")
        return f"Error: Scraping failed: {str(e)}"

@controller.action(
    description="Scrolls the page until a described element becomes visible. "
                "Use when you need to find something that might be below the fold."
)
async def visual_scroll(element_description: str, browser_session: BrowserSession) -> str:
    try:
        page = await browser_session.get_current_page()
        found = await visual_scroll_to(page, element_description)
        if found:
            return f"Scrolled until '{element_description}' became visible."
        else:
            return f"Could not find '{element_description}' after scrolling the entire page."
    except Exception as e:
        logger.error(f"Error in visual_scroll: {e}")
        return f"Error: Visual scroll failed: {str(e)}"

@controller.action(
    description="Takes a screenshot and asks AI to describe everything visible on the current page. "
                "Use this when you're unsure what's on screen or need to understand the page layout."
)
async def visual_describe_page(browser_session: BrowserSession) -> str:
    try:
        page = await browser_session.get_current_page()
        description = await describe_page_visually(page)
        return f"Page description: {description}"
    except Exception as e:
        logger.error(f"Error in visual_describe_page: {e}")
        return f"Error: Could not describe page: {str(e)}"

# ── Dedicated Code Solver Actions ─────────────────────────────────────────────

async def _type_code_into_editor(page, code: str):
    """
    Internal helper: clears the ACE/Monaco editor and sets the code value directly via JavaScript.
    This is the `type_code_fn` callback for code_solver.solve_with_retry().
    """
    js_inject = """
    (code) => {
        try {
            // 1. Try ACE editor (used by Examly)
            const aceEditorEl = document.querySelector('.ace_editor');
            if (aceEditorEl && window.ace) {
                const editor = window.ace.edit(aceEditorEl);
                editor.setValue(code);
                editor.clearSelection();
                return "Successfully set code via ACE editor API";
            }
        } catch (e) {
            console.error("ACE inject error:", e);
        }

        try {
            // 2. Try standard or ACE input textarea/contenteditable
            const tx = document.querySelector('textarea.ace_text-input') || document.querySelector('textarea') || document.querySelector('[contenteditable="true"]');
            if (tx) {
                tx.focus();
                if (tx.tagName === 'TEXTAREA' || tx.tagName === 'INPUT') {
                    tx.value = code;
                } else {
                    tx.innerText = code;
                }
                tx.dispatchEvent(new Event('input', { bubbles: true }));
                tx.dispatchEvent(new Event('change', { bubbles: true }));
                return "Successfully set code via direct DOM value assignment";
            }
        } catch (e) {
            console.error("DOM inject error:", e);
        }

        return "Could not find any suitable editor to inject code";
    }
    """
    res = await page.evaluate(js_inject, code)
    logger.info(f"⚙️ [EDITOR INJECTION RESULT]: {res}")


async def _compile_and_get_verdict(page) -> dict:
    """
    Internal helper: clicks Compile & Run, waits for results, scrapes verdict.
    This is the `compile_and_get_verdict_fn` callback for code_solver.solve_with_retry().

    Returns:
        dict with keys: verdict, details, passed, total
    """
    # Click the "Compile & Run" button
    compile_btn = None
    for selector in [
        '#programme-compile',
        'button',
        '[id*="compile"]',
    ]:
        try:
            elements = await page.get_elements_by_css_selector(selector)
            for el in elements:
                text = await el.evaluate("() => this.innerText")
                if "compile" in text.lower() or "run" in text.lower():
                    compile_btn = el
                    break
            if compile_btn:
                break
        except Exception:
            continue

    if not compile_btn:
        logger.error("[SELF-HEAL] Could not find Compile & Run button!")
        return {"verdict": "ERROR", "details": "Compile button not found", "passed": 0, "total": 0}

    await compile_btn.click()
    logger.info("[SELF-HEAL] Clicked Compile & Run, waiting for results...")

    # Wait for results to appear (the test results panel takes time)
    await asyncio.sleep(8)  # Initial wait for compilation + execution

    # Poll for results — look for the results container
    max_wait = 60  # max seconds to wait for results
    waited = 0
    poll_interval = 3

    while waited < max_wait:
        result_text = ""
        try:
            js_extract_results = """
            () => {
                let text = "";
                const selectors = [
                    '.testcase-result',
                    '.test-case-result',
                    '[class*="testcase"]',
                    '[class*="result"]',
                    '.compilation-result',
                    '#output-panel',
                    '.output-area',
                ];
                for (const sel of selectors) {
                    const elements = document.querySelectorAll(sel);
                    for (const el of elements) {
                        if (el.innerText && el.innerText.trim()) {
                            text += el.innerText.trim() + "\\n";
                        }
                    }
                }
                if (!text) {
                    const bodyText = document.body.innerText;
                    const matches = bodyText.match(/(?:Testcase|Test\\s*Case|Sample)\\s*\\d+\\s*[-:]\\s*(?:Passed|Failed|Error|TLE|Runtime)/gi);
                    if (matches) {
                        text = matches.join("\\n");
                    }
                    const summaryMatch = bodyText.match(/(\\d+)\\s*\\/\\s*(\\d+)\\s*(?:Sample\\s*)?(?:testcase|test\\s*case)s?\\s*passed/i);
                    if (summaryMatch) {
                        text += "\\n" + summaryMatch[0];
                    }
                }
                return text;
            }
            """
            result_text = await page.evaluate(js_extract_results)
        except Exception as e:
            logger.warning(f"[SELF-HEAL] Error reading results: {e}")

        # Parse the results
        if result_text:
            return _parse_verdict(result_text)

        await asyncio.sleep(poll_interval)
        waited += poll_interval

    # Timeout — couldn't get results
    logger.warning("[SELF-HEAL] Timed out waiting for test results")
    return {"verdict": "TIMEOUT", "details": "Timed out waiting for results", "passed": 0, "total": 0}


def _parse_verdict(result_text: str) -> dict:
    """Parse the raw result text from the Examly results panel into a structured verdict."""
    import re

    result_text_lower = result_text.lower()
    details = result_text.strip()

    # Check for compilation error
    if "compilation error" in result_text_lower or "compile error" in result_text_lower:
        return {"verdict": "CE", "details": details, "passed": 0, "total": 0}

    # Check for "X/Y Sample testcase passed" pattern
    summary_match = re.search(
        r'(\d+)\s*/\s*(\d+)\s*(?:sample\s*)?(?:testcase|test\s*case)s?\s*passed',
        result_text_lower,
    )
    if summary_match:
        passed = int(summary_match.group(1))
        total = int(summary_match.group(2))
        if passed == total:
            return {"verdict": "ACCEPTED", "details": details, "passed": passed, "total": total}
        else:
            # Determine the type of failure
            verdict = "WA"  # default
            if "time limit" in result_text_lower or "tle" in result_text_lower:
                verdict = "TLE"
            elif "runtime error" in result_text_lower:
                verdict = "RE"
            return {"verdict": verdict, "details": details, "passed": passed, "total": total}

    # Count individual pass/fail lines
    passed_count = len(re.findall(r'(?:testcase|test\s*case)\s*\d+\s*[-:]\s*passed', result_text_lower))
    failed_count = len(re.findall(r'(?:testcase|test\s*case)\s*\d+\s*[-:]\s*failed', result_text_lower))
    total = passed_count + failed_count

    if total > 0:
        if failed_count == 0:
            return {"verdict": "ACCEPTED", "details": details, "passed": passed_count, "total": total}
        else:
            verdict = "WA"
            if "time limit" in result_text_lower:
                verdict = "TLE"
            elif "runtime error" in result_text_lower:
                verdict = "RE"
            return {"verdict": verdict, "details": details, "passed": passed_count, "total": total}

    # Couldn't parse — return as unknown with the raw text
    return {"verdict": "UNKNOWN", "details": details, "passed": 0, "total": 0}


@controller.action(
    description="SELF-HEALING coding solver. Pass the COMPLETE problem statement and this action handles EVERYTHING automatically: "
                "it generates code, types it into the editor, clicks Compile & Run, reads the verdict, "
                "and if any test cases fail, it fixes the code and retries — up to 3 attempts total. "
                "Returns the final verdict and code. ALWAYS use this for coding questions instead of solving manually. "
                "After this returns, check the verdict: if ACCEPTED, click Submit Code. If still failing after 3 attempts, "
                "submit the best attempt and move on."
)
async def solve_coding_with_retry(problem_statement: str, browser_session: BrowserSession,
                                   language: str = "python") -> str:
    from code_solver import solve_with_retry

    page = await browser_session.get_current_page()

    # Build the callback functions that code_solver will use to drive the browser
    async def type_code_fn(code: str):
        await _type_code_into_editor(page, code)

    async def compile_and_get_verdict_fn():
        return await _compile_and_get_verdict(page)

    # Run the self-healing loop
    result = await solve_with_retry(
        problem_statement=problem_statement,
        type_code_fn=type_code_fn,
        compile_and_get_verdict_fn=compile_and_get_verdict_fn,
        language=language,
    )

    verdict = result["verdict"]
    attempts = result["attempts"]
    passed = result["passed"]
    total = result["total"]

    if verdict == "ACCEPTED" or (total > 0 and passed == total):
        return (
            f"ALL TEST CASES PASSED ({passed}/{total}) on attempt {attempts}. "
            f"Click 'Submit Code' now to submit this solution."
        )
    else:
        return (
            f"BEST ATTEMPT after {attempts} tries: {verdict} ({passed}/{total} test cases passed). "
            f"Click 'Submit Code' to submit this best attempt and move to the next question."
        )

@controller.action(
    description="Types text into an input element character-by-character with a realistic human-like delay (80ms-120ms) "
                "to bypass bot detection. NEVER use standard fill or instant typing actions. "
                "Specify the CSS selector of the input and the text to type."
)
async def human_type(selector: str, text: str, browser_session: BrowserSession) -> str:
    try:
        page = await browser_session.get_current_page()
        elements = await page.get_elements_by_css_selector(selector)
        if not elements:
            return f"Error: Element with selector '{selector}' not found."
        element = elements[0]
        
        # Element.fill handles focus, clearing, and character-by-character typing with delay internally using CDP.
        await element.fill(text, clear=True)
        logger.info(f"⌨️ [HUMAN TYPE]: Typed text into '{selector}'.")
        return f"Successfully typed text into element '{selector}' using CDP fill."
    except Exception as e:
        logger.error(f"Error in human_type: {e}")
        return f"Error: Human typing failed: {str(e)}"


@controller.action(
    description="Injects ALREADY-KNOWN code into the Monaco/ACE editor (e.g., from a saved answer bank lookup). "
                "Use this ONLY when you already have the correct code from lookup_saved_answer. "
                "For NEW coding questions, use solve_coding_with_retry instead — it handles everything."
)
async def inject_code_to_editor(code: str, browser_session: BrowserSession) -> str:
    try:
        page = await browser_session.get_current_page()
        js_inject = """
        (code) => {
            try {
                // 1. Try ACE editor (used by Examly)
                const aceEditorEl = document.querySelector('.ace_editor');
                if (aceEditorEl && window.ace) {
                    const editor = window.ace.edit(aceEditorEl);
                    editor.setValue(code);
                    editor.clearSelection();
                    return "Successfully set code via ACE editor API";
                }
            } catch (e) {
                console.error("ACE inject error:", e);
            }

            try {
                // 2. Try standard or ACE input textarea/contenteditable
                const tx = document.querySelector('textarea.ace_text-input') || document.querySelector('textarea') || document.querySelector('[contenteditable="true"]');
                if (tx) {
                    tx.focus();
                    if (tx.tagName === 'TEXTAREA' || tx.tagName === 'INPUT') {
                        tx.value = code;
                    } else {
                        tx.innerText = code;
                    }
                    tx.dispatchEvent(new Event('input', { bubbles: true }));
                    tx.dispatchEvent(new Event('change', { bubbles: true }));
                    return "Successfully set code via direct DOM value assignment";
                }
            } catch (e) {
                console.error("DOM inject error:", e);
            }

            return "Could not find any suitable editor to inject code";
        }
        """
        res = await page.evaluate(js_inject, code)
        logger.info(f"⚙️ [MONACO/ACE INJECT]: {res}")
        return f"Code injected successfully: {res}"
    except Exception as e:
        logger.error(f"Error in inject_code_to_editor: {e}")
        return f"Error: Code injection failed: {str(e)}"

# ── Answer Bank Actions (Multi-Account Support) ──────────────────────────────

# Global answer bank instance (initialized in main based on --mode)
_answer_bank = None

@controller.action(
    description="Saves a question and its answer to the answer bank for future account runs. "
                "Call this for EVERY question you encounter. Pass question_number (1-indexed), "
                "section (1 or 2), question_type ('mcq' or 'coding'), full question_text, "
                "and your answer (for MCQ) or code (for coding)."
)
async def save_to_answer_bank(question_number: int, section: int, question_type: str,
                               question_text: str, answer: str = "", code: str = "") -> str:
    global _answer_bank
    if _answer_bank:
        _answer_bank.save_question(question_number, section, question_type, question_text, answer, code)
        return f"Saved Q{question_number} (Section {section}, {question_type}) to answer bank."
    return "Answer bank not active. Continuing without saving."

@controller.action(
    description="Records the pass/fail result of a question after compiling or selecting an MCQ answer. "
                "Pass question_number, section, passed (true/false), and any failure details "
                "(e.g., 'Test case 2 failed: expected 5, got 3')."
)
async def record_question_result(question_number: int, section: int, 
                                  passed: bool, details: str = "") -> str:
    global _answer_bank
    if _answer_bank:
        _answer_bank.update_result(question_number, section, passed, details)
        status = "PASSED" if passed else "FAILED"
        return f"Recorded Q{question_number} result: {status}"
    return "Answer bank not active."

@controller.action(
    description="Looks up a saved answer from a previous test run. Pass the first 200 characters "
                "of the question text. In REPLAY mode, ALWAYS call this before solving any question. "
                "If a corrected answer exists, use it directly instead of re-solving."
)
async def lookup_saved_answer(question_text_snippet: str) -> str:
    global _answer_bank
    if _answer_bank:
        result = _answer_bank.get_answer_by_text(question_text_snippet)
        if result:
            q_type = result.get("type", "unknown")
            q_num = result.get("number", "?")
            if q_type == "coding":
                code = result.get("final_code", "")
                if code:
                    return f"FOUND SAVED ANSWER (Coding Q{q_num}, match: {result.get('match_score', 0):.0%}):\n{code}"
            else:
                answer = result.get("final_answer", "")
                if answer:
                    return f"FOUND SAVED ANSWER (MCQ Q{q_num}, match: {result.get('match_score', 0):.0%}): {answer}"
        return "No saved answer found for this question. Solve it normally."
    return "Answer bank not active. Solve normally."

# Load environment variables
load_dotenv()

async def main():
    print("\n--- AI Browser Agent Guided Intake Wizard ---")
    
    # Set up argument parser
    parser = argparse.ArgumentParser(description="General-Purpose Browser Automation Agent with Self-Healing Memory")
    parser.add_argument("--url", help="Target website URL")
    parser.add_argument("--email", help="Login email")
    parser.add_argument("--password", help="Login password")
    parser.add_argument("--task", help="The goal or task description in plain English")
    parser.add_argument("--headless", action="store_true", default=False, help="Run browser in headless mode")
    parser.add_argument("--user-data-dir", default="./agent_profile", help="Path to save cookies/session persistently")
    parser.add_argument("--restore-session", type=str, default=None, help="Restore a previously saved session by ID")
    parser.add_argument("--no-stealth", action="store_true", default=False, help="Disable stealth/anti-detection mode")
    parser.add_argument("--fresh-profile", action="store_true", default=False, help="Delete cached browser profile and start fresh")
    parser.add_argument("--mode", choices=["normal", "discovery", "replay"], default="normal",
                        help="Run mode: normal (default), discovery (save Q&A for review), replay (use saved answers)")
    parser.add_argument("--answer-bank", type=str, default=None,
                        help="Path to answer bank JSON file for discovery/replay modes")
    args, unknown = parser.parse_known_args()
    
    # 1. Determine Target Website URL
    target_url = args.url or os.getenv("TARGET_URL")
    if not target_url:
        target_url = input("Enter target website URL [default: https://mbu931.examly.io/]: ").strip()
    if not target_url:
        target_url = "https://mbu931.examly.io/"
        
    # 2. Determine Task/Goal
    task_goal = args.task
    if not task_goal:
        task_goal = input("What task would you like to perform today? (e.g. 'Take the Day 13 Assessment'): ").strip()
    while not task_goal:
        task_goal = input("Task is required. What would you like to do?: ").strip()

    # Determine platform/domain name
    from urllib.parse import urlparse
    parsed = urlparse(target_url)
    domain = parsed.netloc or parsed.path
    if domain.startswith("www."):
        domain = domain[4:]
    if "/" in domain:
        domain = domain.split("/")[0]
        
    print(f"\nDetecting requirements for site: {domain}...")
    
    # 3. Gather Credentials based on site
    domain_prefix = domain.split('.')[0].upper()
    env_email_key = f"{domain_prefix}_EMAIL"
    env_pass_key = f"{domain_prefix}_PASSWORD"
    
    if "examly" in domain.lower():
        email = args.email or os.getenv("EXAMLY_EMAIL")
        password = args.password or os.getenv("EXAMLY_PASSWORD")
    else:
        email = args.email or os.getenv(env_email_key) or os.getenv("EXAMLY_EMAIL")
        password = args.password or os.getenv(env_pass_key) or os.getenv("EXAMLY_PASSWORD")
        
    # Only ask if completely missing
    if not email:
        email = input(f"Enter username/email for {domain}: ").strip()
    if not password:
        password = input(f"Enter password for {domain}: ").strip()
            
    if not email or not password:
        print("Error: Email and password are required to run the agent.")
        return

    # For Examly, check if COURSE_NAME and TARGET_DATE are present
    course_name = ""
    target_date = ""
    if "examly" in domain.lower():
        course_name = os.getenv("COURSE_NAME")
        if not course_name:
            course_name = input("Enter Examly course name: ").strip()
            
        target_date = os.getenv("TARGET_DATE")
        day_match = re.search(r"Day\s*\d+", task_goal, re.IGNORECASE)
        if day_match:
            parsed_date = day_match.group(0)
            target_date = parsed_date
        if not target_date:
            target_date = input("Enter target assessment date (e.g. Day 13): ").strip()

    # Load persistent agent memory (local JSON knowledge files)
    agent_memory_content = "None"
    try:
        import json
        from pathlib import Path
        knowledge_file = Path("agent_profile") / "knowledge" / f"{domain}.json"
        if knowledge_file.exists():
            entries = json.loads(knowledge_file.read_text())
            if entries:
                lines = []
                for entry in entries:
                    lines.append(f"- Error: {entry.get('error', '?')} | Fix: {entry.get('fix_js', '?')}")
                agent_memory_content = "\n".join(lines)
    except Exception as e:
        logger.warning(f"Could not load agent knowledge: {e}")

    # Check if the website is Examly to append specialized guidelines
    is_examly = "examly.io" in target_url.lower()
    
    # Initialize answer bank if in discovery or replay mode
    run_mode = getattr(args, 'mode', 'normal')
    global _answer_bank
    if run_mode in ("discovery", "replay"):
        from answer_bank import AnswerBank
        bank_test_name = (target_date or "test").replace(" ", "_") + "_Assessment"
        bank_path = getattr(args, 'answer_bank', None) or f"answer_bank_{bank_test_name}.json"
        _answer_bank = AnswerBank(bank_test_name, bank_path)
        loaded_count = len(_answer_bank.questions)
        print(f"[ANSWER BANK] Mode: {run_mode.upper()} | File: {bank_path} | Loaded: {loaded_count} questions")
    
    # Build task instructions. Examly uses the modular structured prompt;
    # other sites use a concise general prompt.
    if is_examly:
        from prompts import build_examly_prompt
        task_instructions = build_examly_prompt(
            task_goal=task_goal,
            target_url=target_url,
            email=email,
            password=password,
            course_name=course_name,
            target_date=target_date,
            run_mode=run_mode,
            agent_memory_content=agent_memory_content,
        )
    else:
        task_instructions = f"""
    You are an automated browser assistant. Your goal is: '{task_goal}'

    Here is the starting configuration:
    - Target URL: {target_url}
    - Credentials: Email/Username is '{email}' and Password is '{password}'

    === GENERAL PLATFORM RULES ===
    1. Navigate to {target_url}
    2. Look for any 'Sign In', 'Log In', or user icon buttons. Click them.
    3. Enter the email '{email}' and password '{password}', then click Login.
    4. CRITICAL: Once logged in, DO NOT look at the profile name (e.g., 'Sameer' or anything else)
       to verify the account. The profile name IS correct. DO NOT click Logout.
       Immediately proceed to find the '{task_goal}'.
    5. Dynamically decide which elements to click, scroll, or input text into to progress towards the goal.
    6. If you hit a blocker you cannot solve, call 'request_user_input' to ask for help in the terminal.
    """

    # Set up models.
    # Navigation brain: lightweight + fast for clicking/reading/navigating.
    nav_model = os.getenv("NAVIGATION_MODEL", "gemini-2.5-flash")
    # Fallback brain: stronger model used when the primary LLM fails repeatedly.
    fallback_model = os.getenv("FALLBACK_MODEL", "gemini-2.5-flash")
    
    if "llama" in nav_model.lower() or "groq" in nav_model.lower() or "mixtral" in nav_model.lower():
        from langchain_groq import ChatGroq
        llm = ChatGroq(
            model=nav_model,
            temperature=0.1,
            max_retries=5,
        )
        object.__setattr__(llm, 'provider', 'groq')
    else:
        llm = ChatGoogle(
            model=nav_model,
            max_retries=5,
            retry_base_delay=3.0,
            retry_max_delay=30.0
        )

    if "llama" in fallback_model.lower() or "groq" in fallback_model.lower() or "mixtral" in fallback_model.lower():
        from langchain_groq import ChatGroq
        fallback_llm = ChatGroq(
            model=fallback_model,
            temperature=0.1,
            max_retries=5,
        )
        object.__setattr__(fallback_llm, 'provider', 'groq')
    else:
        fallback_llm = ChatGoogle(
            model=fallback_model,
            max_retries=5,
            retry_base_delay=5.0,
            retry_max_delay=60.0
        )

    # ── Apply Rate Limiting & Retry Backoff to prevent Gemini 429 ─────────────
    def add_rate_limiter_and_backoff(llm_instance, min_delay=3.0, max_retries=5):
        import time
        import re
        original_ainvoke = llm_instance.ainvoke
        # Keep track of the last time this instance was called
        last_call_time = [0.0]

        async def rate_limited_ainvoke(*args, **kwargs):
            # 1. Global throttling delay between steps
            now = time.time()
            elapsed = now - last_call_time[0]
            if elapsed < min_delay:
                wait_time = min_delay - elapsed
                logger.info(f"⏳ [THROTTLING]: Waiting {wait_time:.2f}s before next request...")
                await asyncio.sleep(wait_time)
            
            # 2. Retry loop with exponential backoff / dynamic sleep
            backoff = 2.0
            for attempt in range(1, max_retries + 1):
                try:
                    last_call_time[0] = time.time()
                    return await original_ainvoke(*args, **kwargs)
                except Exception as e:
                    err_str = str(e)
                    is_rate_limit = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "rate limit" in err_str.lower()
                    
                    if is_rate_limit and attempt < max_retries:
                        # Try to parse exact wait time from API error message (e.g. "Please retry in 53s")
                        match = re.search(r"[Pp]lease retry in ([\d\.]+)\s*s", err_str)
                        if match:
                            wait_time = float(match.group(1)) + 2.0
                            logger.warning(
                                f"⚠️ [429 RATE LIMIT]: Hit rate limit. API requested wait of {match.group(1)}s. "
                                f"Sleeping for {wait_time:.2f}s before attempt {attempt + 1}/{max_retries}..."
                            )
                        else:
                            wait_time = backoff
                            logger.warning(
                                f"⚠️ [429 RATE LIMIT]: Hit rate limit. Exponential backoff: "
                                f"Sleeping for {wait_time:.2f}s before attempt {attempt + 1}/{max_retries}..."
                            )
                            backoff *= 2.0
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"❌ [API ERROR]: Request failed on attempt {attempt}/{max_retries}: {e}")
                        raise e
            
            raise RuntimeError(f"Failed to execute LLM call after {max_retries} retries due to rate limits.")

        llm_instance.ainvoke = rate_limited_ainvoke

    # Only apply rate limiting to Gemini models (Groq has high limits)
    if "gemini" in nav_model.lower():
        add_rate_limiter_and_backoff(llm)
    if "gemini" in fallback_model.lower():
        add_rate_limiter_and_backoff(fallback_llm)


    # ── Initialize Proxy Rotation ─────────────────────────────────────────────
    proxy_rotator = ProxyRotator.from_env()
    proxy_config = proxy_rotator.get_playwright_proxy_config() if proxy_rotator.is_enabled else None
    
    if proxy_config:
        print(f"[PROXY] Proxy rotation enabled with {proxy_rotator.alive_count} proxies.")
    else:
        print("[PROXY] No proxies configured. Using direct connection.")

    # ── Initialize BrowserProfile with Stealth & Proxy ───────────────────────
    stealth_args = get_stealth_browser_args() if not args.no_stealth else ["--disable-blink-features=AutomationControlled"]
    
    # Handle --fresh-profile: delete old cached profile to start clean
    user_data_dir = args.user_data_dir
    if args.fresh_profile and os.path.exists(user_data_dir):
        import shutil
        print(f"[CLEANUP] Deleting old browser profile at '{user_data_dir}'...")
        shutil.rmtree(user_data_dir, ignore_errors=True)
        print("[CLEANUP] Fresh profile will be created.")
    
    browser_profile_kwargs = dict(
        headless=args.headless,
        user_data_dir=user_data_dir,
        disable_security=False,
        args=stealth_args,
    )
    
    # Add proxy if configured
    if proxy_config:
        browser_profile_kwargs["proxy"] = proxy_config
    
    browser_profile = BrowserProfile(**browser_profile_kwargs)
    browser = BrowserSession(browser_profile=browser_profile)

    # ── Initialize the Agent ─────────────────────────────────────────────────
    agent = Agent(
        task=task_instructions,
        llm=llm,
        fallback_llm=fallback_llm,
        controller=controller,
        browser_session=browser,
        max_failures=10,
        max_actions_per_step=5,
    )
    
    # ── Apply Stealth & Restore Session ──────────────────────────────────────
    print(f"\nFiring up the browser and starting task '{task_goal}' on '{target_url}'...")
    
    if not args.no_stealth:
        print("[STEALTH] Stealth mode: ENABLED (anti-bot protections active)")
    
    # Run the agent locally
    result = await agent.run()

    # ── Report Result ──────────────────────────────────────────────────────
    print("\n--- Agent Execution Finished ---")
    if result.is_successful():
        print("Success! Final result:")
    else:
        print("Agent finished (or stopped). Final message:")

    # Safely print the final result without dumping massive objects to Windows terminal
    final_output = result.final_result()
    if final_output:
        print(final_output.encode('ascii', 'ignore').decode('ascii'))
    else:
        print("No final output string returned.")

if __name__ == "__main__":
    asyncio.run(main())
