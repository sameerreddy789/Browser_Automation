"""
ai_consultant.py — AI-powered terminal consultant for the browser agent.

When the browser agent encounters a blocker it can't solve on its own, it can
consult an AI model (via the Gemini API) for help. This replaces the old
PocketBase/Streamlit HITL dashboard with a lightweight terminal-based flow:

    Agent prints question → Human responds, OR types 'ai' →
    AI consultant (via API) answers → Agent continues.

This module is the "API answer" half. The terminal I/O half lives in main.py's
`request_user_input` controller action.

Usage:
    from ai_consultant import consult_ai, consult_ai_with_vision

    # Text-only consultation
    answer = await consult_ai("How do I dismiss this modal overlay?")

    # Vision consultation (with a screenshot)
    answer = await consult_ai_with_vision(
        "Which option should I select for this CAPTCHA?",
        image_path="debug_blocked.png",
    )
"""

import base64
import os
from google import genai
from loguru import logger

logger = logger.bind(name="browser_use.ai_consultant")

# The consultant model — override via CONSULTANT_MODEL env var.
# Default to gemini-3.1-flash-lite.
CONSULTANT_MODEL = os.getenv("CONSULTANT_MODEL", "gemini-3.1-flash-lite")

SYSTEM_PROMPT = """You are an AI assistant helping a browser automation agent.
The agent is taking an online test on the MBU Examly platform and has hit a blocker
it cannot resolve on its own.

Provide a CONCISE, ACTIONABLE answer.
- If the question is about a CAPTCHA: describe exactly what characters/text you see.
- If it's a page layout / selector issue: suggest specific CSS selectors or actions.
- If it's a coding problem: give the solution approach (or full code if short).
- If it's a login/auth issue: suggest specific step-by-step actions.

Keep your answer under 3-4 sentences unless code is required. Be direct — the agent
will read your answer verbatim and act on it."""


async def consult_ai(question: str, context: str = "") -> str:
    """
    Ask the AI consultant a question (text only).

    Args:
        question: The question or blocker description from the browser agent.
        context: Optional extra context (page state, prior actions, error text).

    Returns:
        The AI's answer as a string.
    """
    client = genai.Client()

    prompt = f"{SYSTEM_PROMPT}\n\nQuestion from agent: {question}"
    if context:
        prompt += f"\nAdditional context: {context}"

    try:
        response = client.models.generate_content(
            model=CONSULTANT_MODEL,
            contents=prompt,
            config={"temperature": 0.3},
        )
        answer = response.text.strip()
        logger.info(f"🤖 [AI CONSULTANT]: {answer[:100]}...")
        return answer
    except Exception as e:
        logger.error(f"❌ [AI CONSULTANT]: Failed to answer: {e}")
        return f"[AI consultant error: {e}]"


async def consult_ai_with_vision(question: str, image_path: str) -> str:
    """
    Ask the AI consultant with a screenshot for visual context.

    Args:
        question: The question from the browser agent.
        image_path: Path to a PNG screenshot of the current page state.

    Returns:
        The AI's answer as a string.
    """
    client = genai.Client()

    try:
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        response = client.models.generate_content(
            model=CONSULTANT_MODEL,
            contents=[
                {
                    "role": "user",
                    "parts": [
                        {"text": f"{SYSTEM_PROMPT}\n\nQuestion from agent: {question}"},
                        {"inline_data": {"mime_type": "image/png", "data": image_data}},
                    ],
                }
            ],
            config={"temperature": 0.3},
        )
        answer = response.text.strip()
        logger.info(f"🤖 [AI CONSULTANT+VISION]: {answer[:100]}...")
        return answer
    except Exception as e:
        logger.error(f"❌ [AI CONSULTANT+VISION]: Vision query failed: {e}")
        return f"[AI consultant vision error: {e}]"
