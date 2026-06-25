"""
replay_direct.py — Zero-API Replay Script (Pure Playwright)

Takes the Examly assessment using ONLY saved answers from the answer bank.
No LLM calls. No API quota. No rate limits. Just fast, dumb automation.

How it works:
1. Opens a stealth Chromium browser
2. Logs into Examly with the given credentials
3. Navigates to the course → day → assessment
4. For each question: reads text from DOM → fuzzy-matches answer bank → clicks the option
5. Handles section switching (if multiple sections)
6. Submits the test

Usage:
    # Single account
    uv run python replay_direct.py --email user@example.com --password pass123 --day "Day 26"

    # All accounts from .env (skips Account 1 sacrifice)
    uv run python replay_direct.py --day "Day 26" --all-accounts
"""

import asyncio
import argparse
import json
import os
import re
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeout
from stealth import get_stealth_browser_args

load_dotenv()


# ── Answer Bank Matcher ───────────────────────────────────────────────────────

def load_answer_bank(file_path: str) -> dict:
    """Load the answer bank JSON file."""
    if not os.path.exists(file_path):
        print(f"  ❌ Answer bank not found: {file_path}")
        sys.exit(1)
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    questions = data.get("questions", {})
    print(f"  📂 Loaded {len(questions)} answers from {file_path}")
    return questions


def normalize_text(text: str) -> str:
    """Normalize text for matching — lowercase, collapse whitespace, strip."""
    return re.sub(r'\s+', ' ', text.strip().lower())


def find_answer(questions: dict, question_text: str) -> dict | None:
    """
    Find a saved answer by fuzzy word-overlap matching.
    Same algorithm as answer_bank.py but standalone (no imports needed).
    """
    normalized_query = normalize_text(question_text[:300])
    query_words = set(normalized_query.split())

    if not query_words:
        return None

    best_match = None
    best_score = 0

    for key, q_data in questions.items():
        saved_snippet = q_data.get("text_snippet", "")
        if not saved_snippet:
            continue
        saved_words = set(saved_snippet.split())
        if not saved_words:
            continue

        # Jaccard similarity
        common = query_words & saved_words
        union = query_words | saved_words
        score = len(common) / len(union) if union else 0

        if score > best_score and score > 0.4:
            best_score = score
            best_match = q_data

    if best_match:
        # Corrected answer takes priority over original
        result = dict(best_match)
        result["final_answer"] = (
            result.get("corrected_answer") or result.get("answer") or ""
        )
        result["final_code"] = (
            result.get("corrected_code") or result.get("code") or ""
        )
        result["match_score"] = best_score
        return result

    return None


# ── Examly Navigation (Pure Playwright) ───────────────────────────────────────

async def wait_and_click(page: Page, selector: str, timeout: int = 15000, label: str = ""):
    """Wait for element to appear, then click it."""
    try:
        await page.wait_for_selector(selector, state="visible", timeout=timeout)
        await page.click(selector)
        if label:
            print(f"    ✅ Clicked: {label}")
        return True
    except PlaywrightTimeout:
        print(f"    ⚠️  Timeout waiting for: {label or selector}")
        return False


async def wait_for_text(page: Page, text: str, timeout: int = 15000) -> bool:
    """Wait for specific text to appear on the page."""
    try:
        await page.wait_for_function(
            f"document.body.innerText.includes('{text}')",
            timeout=timeout
        )
        return True
    except PlaywrightTimeout:
        return False


async def login(page: Page, email: str, password: str) -> bool:
    """Log into Examly."""
    print("\n  🔐 Logging in...")

    # Check if already logged in (dashboard visible)
    try:
        current_url = page.url
        if "dashboard" in current_url or "home" in current_url:
            # Check if the right account is logged in
            print("    ℹ️  Already on dashboard, checking account...")
            # Try to find the user profile/name element
            try:
                profile_el = await page.query_selector('[class*="profile"] span, [class*="user"] span, .nav-link.dropdown-toggle')
                if profile_el:
                    profile_text = await profile_el.inner_text()
                    print(f"    👤 Logged in as: {profile_text}")
            except Exception:
                pass
            # Log out first to ensure clean state
            print("    🔄 Logging out for clean login...")
            try:
                await page.click('[class*="profile"], [class*="user-dropdown"], .nav-link.dropdown-toggle')
                await asyncio.sleep(1)
                logout_el = await page.query_selector('text=Logout, text=Log out, text=Sign out')
                if logout_el:
                    await logout_el.click()
                    await asyncio.sleep(3)
            except Exception:
                pass
    except Exception:
        pass

    # Navigate to login page
    await page.goto("https://mbu931.examly.io/", wait_until="networkidle", timeout=30000)
    await asyncio.sleep(2)

    # Enter email
    email_input = await page.query_selector('input[type="email"], input[type="text"], input[name="email"], #email')
    if not email_input:
        # Try to find any visible input
        email_input = await page.query_selector('input:visible')
    
    if email_input:
        await email_input.click()
        await email_input.fill("")
        await email_input.type(email, delay=20)
        await email_input.dispatch_event("input")
        print(f"    ✅ Entered email: {email}")
    else:
        print("    ❌ Could not find email input!")
        return False

    await asyncio.sleep(1)

    # Click Next / Continue button
    next_clicked = False
    for selector in ['button:has-text("Next")', 'button:has-text("Continue")', 'button[type="submit"]', 'button:has-text("next")', '#next-btn']:
        try:
            btn = await page.query_selector(selector)
            if btn and await btn.is_visible():
                await btn.click()
                next_clicked = True
                print("    ✅ Clicked Next")
                break
        except Exception:
            continue

    if not next_clicked:
        # Try pressing Enter
        await page.keyboard.press("Enter")
        print("    ✅ Pressed Enter (no Next button found)")

    # Enter password
    password_input = None
    try:
        password_input = await page.wait_for_selector('input[type="password"]', state="visible", timeout=15000)
    except PlaywrightTimeout:
        pass
        
    if password_input:
        if not password:
            print("    ❌ Password variable is empty!")
            return False
        await password_input.click()
        await password_input.fill("")
        await password_input.type(password, delay=100) # Slower typing for Angular
        await password_input.dispatch_event("input")
        print("    ✅ Entered password")
        await asyncio.sleep(1)
        await page.screenshot(path="debug_after_password.png")
    else:
        print("    ❌ Could not find password input!")
        return False

    await asyncio.sleep(1)

    # Click Login button
    login_clicked = False
    for selector in ['button:has-text("Login")', 'button:has-text("Sign in")', 'button:has-text("Log in")', 'button[type="submit"]', '#login-btn']:
        try:
            btn = await page.query_selector(selector)
            if btn and await btn.is_visible():
                await btn.click()
                login_clicked = True
                print("    ✅ Clicked Login")
                break
        except Exception:
            continue

    if not login_clicked:
        await page.keyboard.press("Enter")
        print("    ✅ Pressed Enter (no Login button found)")

    # Wait for dashboard to load
    await asyncio.sleep(5)

    # Verify login success
    current_url = page.url
    if "login" in current_url.lower() or "signin" in current_url.lower() or current_url.strip("/") == "https://mbu931.examly.io":
        print("    ❌ Login may have failed (still on login page)")
        # Take a screenshot for debugging
        await page.screenshot(path="debug_login_failed.png")
        return False

    print("    ✅ Login successful!")
    return True


async def navigate_to_assessment(page: Page, course_name: str, target_date: str) -> bool:
    """Navigate from dashboard to the specific day's assessment."""
    print(f"\n  📚 Navigating to {target_date} Assessment...")

    # Step 1: Click Courses in sidebar
    await asyncio.sleep(2)
    courses_clicked = False
    for selector in ['text=Courses', 'a:has-text("Courses")', '[href*="course"]', 'text=courses']:
        try:
            el = await page.query_selector(selector)
            if el and await el.is_visible():
                await el.click()
                courses_clicked = True
                print("    ✅ Clicked Courses")
                break
        except Exception:
            continue

    if not courses_clicked:
        print("    ⚠️  Could not find Courses link, trying to continue anyway...")

    await asyncio.sleep(3)

    # Step 2: Find and click the specific course
    course_clicked = False
    # Try exact text match first
    try:
        course_el = await page.query_selector(f'text="{course_name}"')
        if not course_el:
            # Try partial match
            course_el = await page.query_selector('text=60 days')
        if not course_el:
            course_el = await page.query_selector('text=Skill Development')
        if course_el:
            await course_el.click()
            course_clicked = True
            print("    ✅ Clicked course")
    except Exception as e:
        print(f"    ⚠️  Error clicking course: {e}")

    if not course_clicked:
        # Try clicking any card that might be the course
        try:
            cards = await page.query_selector_all('.card, [class*="course"]')
            for card in cards:
                text = await card.inner_text()
                if "60 days" in text or "Skill Development" in text:
                    await card.click()
                    course_clicked = True
                    print("    ✅ Clicked course card")
                    break
        except Exception:
            pass

    await asyncio.sleep(3)

    # Step 3: Find the day dropdown and click it
    day_clicked = False
    # Extract day number for flexible matching
    day_number = re.search(r'\d+', target_date)
    day_num = day_number.group(0) if day_number else target_date

    # Try multiple strategies to find the day
    for attempt in range(3):
        try:
            # Strategy 1: Look for exact text
            day_el = await page.query_selector(f'text="{target_date}"')
            if not day_el:
                # Strategy 2: Look for text containing the day
                day_el = await page.query_selector(f'text="Day {day_num}"')
            if not day_el:
                # Strategy 3: Get all expandable items and find the right one
                items = await page.query_selector_all('[class*="accordion"], [class*="collapse"], [class*="expand"], [class*="dropdown"], [role="button"]')
                for item in items:
                    text = await item.inner_text()
                    if f"Day {day_num}" in text or target_date in text:
                        day_el = item
                        break

            if day_el:
                await day_el.click()
                day_clicked = True
                print(f"    ✅ Clicked {target_date} dropdown")
                break
        except Exception:
            pass

        # Scroll down and try again
        await page.evaluate("window.scrollBy(0, 300)")
        await asyncio.sleep(1)

    if not day_clicked:
        print(f"    ❌ Could not find {target_date} dropdown!")
        await page.screenshot(path="debug_day_not_found.png")
        return False

    await asyncio.sleep(2)

    # Step 4: Click the Assessment link
    assessment_clicked = False
    for selector in [f'text="{target_date} Assessment"', f'text="{target_date} assessment"', 'text="Assessment"', 'text="1. "']:
        try:
            el = await page.query_selector(selector)
            if el and await el.is_visible():
                await el.click()
                assessment_clicked = True
                print("    ✅ Clicked Assessment link")
                break
        except Exception:
            continue

    if not assessment_clicked:
        # Try clicking any link that appeared after expanding the day
        try:
            links = await page.query_selector_all('a, button')
            for link in links:
                text = await link.inner_text()
                if "assessment" in text.lower() and (day_num in text or target_date.lower() in text.lower()):
                    await link.click()
                    assessment_clicked = True
                    print(f"    ✅ Clicked: {text.strip()[:50]}")
                    break
        except Exception:
            pass

    await asyncio.sleep(3)

    # Step 5: Click "Take Test" or "Resume Test"
    for selector in ['text="Take Test"', 'text="Resume Test"', 'text="Start Test"', 'button:has-text("Take")', 'button:has-text("Resume")', 'button:has-text("Start")']:
        try:
            el = await page.query_selector(selector)
            if el and await el.is_visible():
                await el.click()
                print("    ✅ Clicked Take/Resume Test")
                break
        except Exception:
            continue

    await asyncio.sleep(3)

    # Step 6: Click "Agree and proceed" or similar
    for selector in ['text="Agree"', 'button:has-text("Agree")', 'button:has-text("Proceed")', 'text="I agree"', 'button:has-text("agree")']:
        try:
            el = await page.query_selector(selector)
            if el and await el.is_visible():
                await el.click()
                print("    ✅ Clicked Agree")
                break
        except Exception:
            continue

    await asyncio.sleep(5)
    print("    ✅ Assessment loaded!")
    return True


async def get_question_text(page: Page) -> str:
    """Extract the current question text from the DOM."""
    # Try multiple selectors for question text
    selectors = [
        '.question-text',
        '.question-content',
        '[class*="question"] p',
        '[class*="question-desc"]',
        '.ql-editor',
        '[class*="ques"]',
        '.problem-statement',
    ]

    for selector in selectors:
        try:
            el = await page.query_selector(selector)
            if el:
                text = await el.inner_text()
                if text and len(text.strip()) > 20:
                    return text.strip()
        except Exception:
            continue

    # Fallback: get all visible text from the main content area
    try:
        main = await page.query_selector('main, [class*="content"], [class*="body"]')
        if main:
            text = await main.inner_text()
            return text.strip()
    except Exception:
        pass

    return ""


async def get_mcq_options(page: Page) -> list[dict]:
    """Get all MCQ option elements and their text."""
    options = []
    # Try multiple selectors for MCQ options
    option_selectors = [
        '.option-item',
        '[class*="option"]',
        '[class*="choice"]',
        'label[for*="option"]',
        '[class*="answer-option"]',
        '.mat-radio-button',
        'input[type="radio"] + label',
        'input[type="radio"]',
    ]

    for selector in option_selectors:
        try:
            elements = await page.query_selector_all(selector)
            if elements and len(elements) >= 2:
                for el in elements:
                    text = await el.inner_text()
                    if text and text.strip():
                        options.append({"element": el, "text": text.strip()})
                if options:
                    return options
        except Exception:
            continue

    return options


async def select_mcq_answer(page: Page, options: list[dict], answer: str) -> bool:
    """Select the correct MCQ option by matching the answer text."""
    answer_lower = normalize_text(answer)

    # Strategy 1: Exact match
    for opt in options:
        opt_text = normalize_text(opt["text"])
        if answer_lower == opt_text or answer_lower in opt_text or opt_text in answer_lower:
            await opt["element"].click()
            return True

    # Strategy 2: The answer might be like "BDCA" — look for option containing it
    for opt in options:
        opt_text = opt["text"].strip()
        if answer in opt_text or opt_text in answer:
            await opt["element"].click()
            return True

    # Strategy 3: The answer is a short code like "BDCA" — match it anywhere in option text
    if len(answer) <= 10:
        for opt in options:
            if answer.upper() in opt["text"].upper():
                await opt["element"].click()
                return True

    # Strategy 4: First word/token match
    for opt in options:
        opt_first = opt["text"].strip().split()[0] if opt["text"].strip() else ""
        if opt_first and (opt_first == answer or answer.startswith(opt_first)):
            await opt["element"].click()
            return True

    return False


async def inject_code(page: Page, code: str) -> bool:
    """Inject code into Monaco editor."""
    # Escape the code for JavaScript injection
    escaped_code = code.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")

    js = f"""
    (function() {{
        try {{
            if (window.monaco && window.monaco.editor) {{
                const models = window.monaco.editor.getModels();
                if (models && models.length > 0) {{
                    models[0].setValue(`{escaped_code}`);
                    const textarea = document.querySelector('.monaco-editor textarea');
                    if (textarea) textarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    return "Monaco updated";
                }}
            }}
            const el = document.querySelector('textarea, div[contenteditable="true"]');
            if (el) {{
                el.value = `{escaped_code}`;
                el.innerText = `{escaped_code}`;
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                return "Fallback editor updated";
            }}
            return "No editor found";
        }} catch(e) {{
            return "Error: " + e.toString();
        }}
    }})()
    """
    result = await page.evaluate(js)
    return "updated" in str(result).lower()


async def click_next_question(page: Page) -> bool:
    """Click the next question button or navigate to the next question."""
    for selector in [
        'button:has-text("Next")',
        'button:has-text("Save & Next")',
        'button:has-text("Save and Next")',
        '#next-btn',
        '[class*="next"]',
        'button:has-text(">>") ',
        'button:has-text(">")',
    ]:
        try:
            el = await page.query_selector(selector)
            if el and await el.is_visible():
                await el.click()
                return True
        except Exception:
            continue
    return False


async def get_current_question_number(page: Page) -> int:
    """Try to figure out which question number we're on."""
    try:
        # Look for question number indicators
        for selector in ['[class*="question-number"]', '[class*="q-num"]', '[class*="qno"]', '.active[class*="question"]']:
            el = await page.query_selector(selector)
            if el:
                text = await el.inner_text()
                nums = re.findall(r'\d+', text)
                if nums:
                    return int(nums[0])
    except Exception:
        pass
    return 0


async def get_total_questions(page: Page) -> int:
    """Try to get the total number of questions."""
    try:
        # Look for "Q X of Y" or similar patterns
        body_text = await page.inner_text('body')
        patterns = [
            r'of\s+(\d+)\s+question',
            r'(\d+)\s+question',
            r'/\s*(\d+)',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, body_text, re.IGNORECASE)
            if matches:
                return max(int(m) for m in matches)
    except Exception:
        pass
    return 30  # Default based on known test structure


async def check_and_switch_section(page: Page, current_section: int) -> int:
    """Check if there are multiple sections and switch if needed."""
    try:
        # Look for section dropdown/indicator
        section_els = await page.query_selector_all('[class*="section"], [class*="Section"]')
        for el in section_els:
            text = await el.inner_text()
            match = re.search(r'(\d+)\s*/\s*(\d+)', text)
            if match:
                current = int(match.group(1))
                total = int(match.group(2))
                if current < total:
                    print(f"\n  📋 Section {current}/{total} — switching to Section {current + 1}...")
                    await el.click()
                    await asyncio.sleep(1)
                    # Try to click the next section
                    next_section = await page.query_selector(f'text="Section {current + 1}"')
                    if next_section:
                        await next_section.click()
                        await asyncio.sleep(2)
                        return current + 1
    except Exception:
        pass
    return current_section


async def submit_test(page: Page) -> bool:
    """Submit the test and type END."""
    print("\n  📤 Submitting test...")

    # Click Submit Test button
    for selector in ['button:has-text("Submit Test")', 'button:has-text("Submit")', '#submit-test', 'button:has-text("Finish")']:
        try:
            el = await page.query_selector(selector)
            if el and await el.is_visible():
                await el.click()
                print("    ✅ Clicked Submit Test")
                break
        except Exception:
            continue

    await asyncio.sleep(3)

    # Look for confirmation dialog — type END
    try:
        end_input = await page.query_selector('input[placeholder*="END"], input[type="text"]')
        if end_input and await end_input.is_visible():
            await end_input.fill("END")
            await end_input.dispatch_event("input")
            print("    ✅ Typed END")
            await asyncio.sleep(1)

            # Click final submit
            for selector in ['button:has-text("Submit")', 'button:has-text("Confirm")', 'button:has-text("Yes")']:
                try:
                    btn = await page.query_selector(selector)
                    if btn and await btn.is_visible():
                        await btn.click()
                        print("    ✅ Final submit clicked")
                        break
                except Exception:
                    continue
        else:
            # Try JS injection for END input
            await page.evaluate("""
                const endInput = Array.from(document.querySelectorAll('input')).find(
                    el => el.placeholder.includes('END') || el.type === 'text'
                );
                if (endInput) {
                    endInput.value = 'END';
                    endInput.dispatchEvent(new Event('input', { bubbles: true }));
                }
            """)
            print("    ✅ Typed END via JS injection")
            await asyncio.sleep(1)

            # Click final submit
            for selector in ['button:has-text("Submit")', 'button:has-text("Confirm")']:
                try:
                    btn = await page.query_selector(selector)
                    if btn and await btn.is_visible():
                        await btn.click()
                        print("    ✅ Final submit clicked")
                        break
                except Exception:
                    continue
    except Exception as e:
        print(f"    ⚠️  Error during END input: {e}")

    await asyncio.sleep(5)
    print("    ✅ Test submitted!")
    return True


# ── Main Replay Loop ─────────────────────────────────────────────────────────

async def replay_test(email: str, password: str, target_date: str,
                       course_name: str, answer_bank: dict, headless: bool = False):
    """Run the complete test replay for a single account."""
    print(f"\n{'='*60}")
    print(f"  🎯 REPLAY: {email}")
    print(f"  📝 Test: {target_date} Assessment")
    print(f"  📂 Answers loaded: {len(answer_bank)}")
    print(f"{'='*60}")

    stealth_args = get_stealth_browser_args()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=stealth_args,
        )
        context = await browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )
        page = await context.new_page()

        try:
            # Step 1: Login
            if not await login(page, email, password):
                print("  ❌ Login failed! Skipping this account.")
                await page.screenshot(path=f"debug_login_{email.split('@')[0]}.png")
                return False

            # Step 2: Navigate to the assessment
            if not await navigate_to_assessment(page, course_name, target_date):
                print("  ❌ Navigation failed! Skipping this account.")
                await page.screenshot(path=f"debug_nav_{email.split('@')[0]}.png")
                return False

            # Step 3: Answer all questions
            answered = 0
            failed = 0
            current_section = 1
            total_q = len(answer_bank)

            for q_num in range(1, total_q + 1):
                await asyncio.sleep(2)  # Let the page settle

                # Read question text
                q_text = await get_question_text(page)

                if not q_text or len(q_text) < 10:
                    print(f"    ⚠️  Q{q_num}: Could not read question text, trying to proceed...")
                    await click_next_question(page)
                    failed += 1
                    continue

                # Look up answer
                match = find_answer(answer_bank, q_text)

                if not match:
                    print(f"    ⚠️  Q{q_num}: No matching answer found (score too low)")
                    await click_next_question(page)
                    failed += 1
                    continue

                q_type = match.get("type", "mcq")
                match_score = match.get("match_score", 0)
                print(f"    📝 Q{q_num}: Matched (score: {match_score:.0%}, type: {q_type})")

                if q_type == "mcq":
                    answer = match.get("final_answer", "")
                    if answer:
                        options = await get_mcq_options(page)
                        if options:
                            selected = await select_mcq_answer(page, options, answer)
                            if selected:
                                print(f"    ✅ Q{q_num}: Selected '{answer}'")
                                answered += 1
                            else:
                                print(f"    ⚠️  Q{q_num}: Could not find option matching '{answer}'")
                                # Try clicking by text directly on the page
                                try:
                                    opt_el = await page.query_selector(f'text="{answer}"')
                                    if opt_el:
                                        await opt_el.click()
                                        print(f"    ✅ Q{q_num}: Selected via text match")
                                        answered += 1
                                    else:
                                        failed += 1
                                except Exception:
                                    failed += 1
                        else:
                            print(f"    ⚠️  Q{q_num}: No MCQ options found on page")
                            failed += 1
                    else:
                        print(f"    ⚠️  Q{q_num}: No answer text in bank")
                        failed += 1

                elif q_type == "coding":
                    code = match.get("final_code", "")
                    if code:
                        # Select Python 3 language
                        try:
                            lang_dropdown = await page.query_selector('select[class*="lang"], [class*="language"] select')
                            if lang_dropdown:
                                await lang_dropdown.select_option(label="Python 3")
                                await asyncio.sleep(1)
                        except Exception:
                            pass

                        if await inject_code(page, code):
                            print(f"    ✅ Q{q_num}: Code injected")
                            await asyncio.sleep(1)

                            # Click Compile & Run
                            compile_btn = await page.query_selector('#programme-compile, button:has-text("Compile"), button:has-text("Run")')
                            if compile_btn:
                                await compile_btn.click()
                                print(f"    ⏳ Q{q_num}: Compiling...")
                                await asyncio.sleep(10)

                            # Click Submit Code
                            submit_btn = await page.query_selector('#tt-footer-submit-answer, #tt-footer-submit-ans, button:has-text("Submit Code")')
                            if submit_btn:
                                await submit_btn.click()
                                print(f"    ✅ Q{q_num}: Code submitted")
                                await asyncio.sleep(2)

                                # Handle confirmation dialog
                                for sel in ['button:has-text("Yes")', 'button:has-text("OK")', 'button:has-text("Confirm")']:
                                    try:
                                        btn = await page.query_selector(sel)
                                        if btn and await btn.is_visible():
                                            await btn.click()
                                            break
                                    except Exception:
                                        continue

                            answered += 1
                        else:
                            print(f"    ⚠️  Q{q_num}: Code injection failed")
                            failed += 1
                    else:
                        print(f"    ⚠️  Q{q_num}: No code in bank")
                        failed += 1

                # Move to next question
                await asyncio.sleep(1)
                if q_num < total_q:
                    await click_next_question(page)
                    await asyncio.sleep(1)

            # Check for additional sections
            new_section = await check_and_switch_section(page, current_section)
            if new_section > current_section:
                print(f"\n  📋 Additional section {new_section} found — but all questions were in bank already")

            # Step 4: Submit the test
            await submit_test(page)

            print(f"\n  📊 Results: {answered}/{total_q} answered, {failed} failed")
            print(f"  ✅ Replay complete for {email}!")

        except Exception as e:
            print(f"\n  ❌ Error during replay: {e}")
            await page.screenshot(path=f"debug_error_{email.split('@')[0]}.png")
            return False
        finally:
            await browser.close()

    return True


# ── CLI Entry Point ───────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="Zero-API Examly Replay (Pure Playwright)")
    parser.add_argument("--email", help="Login email")
    parser.add_argument("--password", help="Login password")
    parser.add_argument("--day", type=str, required=True, help="Target date (e.g., 'Day 26')")
    parser.add_argument("--course", type=str, help="Course name to navigate to")
    parser.add_argument("--headless", action="store_true", help="Run browser without visible window")
    parser.add_argument("--all-accounts", action="store_true", help="Run for all accounts in .env (skip Account 1)")
    parser.add_argument("--all-accounts-include-first", action="store_true", help="Run for ALL accounts including Account 1")
    parser.add_argument("--answer-bank", help="Path to answer bank JSON (auto-detected if not specified)")
    args = parser.parse_args()

    target_date = args.day
    course_name = args.course or os.getenv("COURSE_NAME", "2028_MBU_60 days Skill Development Assessment Course")

    # Auto-detect answer bank file
    test_name = target_date.replace(" ", "_") + "_Assessment"
    bank_file = args.answer_bank or f"answer_bank_{test_name}.json"
    answer_bank = load_answer_bank(bank_file)

    if args.all_accounts or args.all_accounts_include_first:
        # Run for multiple accounts
        accounts = []
        i = 1
        while True:
            email = os.getenv(f"ACCOUNT_{i}_EMAIL")
            password = os.getenv(f"ACCOUNT_{i}_PASS")
            if not email or not password:
                break
            accounts.append({"email": email, "password": password})
            i += 1

        if not accounts:
            print("❌ No accounts found in .env!")
            return

        # Skip Account 1 (sacrifice) unless --all-accounts-include-first
        start_idx = 0 if args.all_accounts_include_first else 1
        target_accounts = accounts[start_idx:]

        print(f"\n{'='*60}")
        print("  🤖 Zero-API Multi-Account Replay")
        print(f"{'='*60}")
        print(f"  Test: {target_date} Assessment")
        print(f"  Accounts: {len(target_accounts)}")
        print(f"  Answer Bank: {bank_file} ({len(answer_bank)} questions)")
        print("  API Calls: ZERO 🎉")
        print(f"{'='*60}")

        for account in target_accounts:
            await replay_test(
                account["email"], account["password"],
                target_date, course_name, answer_bank,
                headless=args.headless
            )

        print(f"\n{'='*60}")
        print("  ✅ ALL ACCOUNTS COMPLETED!")
        print(f"{'='*60}\n")

    else:
        # Single account
        email = args.email or os.getenv("EXAMLY_EMAIL")
        password = args.password or os.getenv("EXAMLY_PASSWORD")

        if not email or not password:
            print("❌ Email and password required! Use --email and --password, or set in .env")
            return

        await replay_test(email, password, target_date, course_name, answer_bank, headless=args.headless)


if __name__ == "__main__":
    asyncio.run(main())
