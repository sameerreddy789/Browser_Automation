"""
session_store.py — Local JSON Session Storage

Backs up browser cookies so the bot can restore logins across runs.
Pure local JSON file storage — no external services required.

Usage:
    from session_store import SessionStore

    store = SessionStore()

    # After logging in, save the session
    await store.backup_session(browser_context, "examly_main")

    # On next run, restore the session
    await store.restore_session(browser_context, "examly_main")
"""

import json
import os
from datetime import datetime
from typing import Optional
from loguru import logger

logger = logger.bind(name="browser_use.session_store")

# Directory for local JSON session storage
SESSIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions")


class SessionStore:
    """
    Browser session backup/restore using local JSON files.

    Like a "save game" for logins: save cookies after a successful login,
    load them back next time to skip the login flow.
    """

    def __init__(self):
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        logger.info(f"ℹ️ [SESSION STORE]: Using local JSON storage in {SESSIONS_DIR}/")

    async def backup_session(self, context, session_id: str, ttl_seconds: int = 86400) -> bool:
        """
        Extract cookies from a Playwright browser context and save them locally.

        Args:
            context: Playwright BrowserContext object.
            session_id: A name for this session (e.g., "examly_main").
            ttl_seconds: Kept for API compatibility (ignored by local store).

        Returns:
            True if backup succeeded, False otherwise.
        """
        try:
            cookies = await context.cookies()
            session_data = {
                "session_id": session_id,
                "cookies": cookies,
                "saved_at": datetime.now().isoformat(),
                "cookie_count": len(cookies),
            }
            serialized = json.dumps(session_data, indent=2, default=str)
            self._save_local(session_id, serialized)
            return True
        except Exception as e:
            logger.error(f"❌ [SESSION STORE]: Failed to backup session '{session_id}': {e}")
            return False

    async def restore_session(self, context, session_id: str) -> bool:
        """
        Load saved cookies and inject them into a Playwright browser context.

        Args:
            context: Playwright BrowserContext object.
            session_id: The name of the session to restore.

        Returns:
            True if restore succeeded, False if session not found or failed.
        """
        try:
            session_data = self._load_session(session_id)
            if session_data is None:
                logger.info(f"ℹ️ [SESSION STORE]: No saved session found for '{session_id}'.")
                return False

            cookies = session_data.get("cookies", [])
            if not cookies:
                logger.warning(f"⚠️ [SESSION STORE]: Session '{session_id}' exists but has no cookies.")
                return False

            await context.add_cookies(cookies)
            saved_at = session_data.get("saved_at", "unknown")
            logger.info(
                f"✅ [SESSION STORE]: Restored {len(cookies)} cookies for session '{session_id}' "
                f"(saved at: {saved_at})"
            )
            return True
        except Exception as e:
            logger.error(f"❌ [SESSION STORE]: Failed to restore session '{session_id}': {e}")
            return False

    def list_sessions(self) -> list[dict]:
        """List all saved sessions with metadata."""
        sessions = []
        if os.path.exists(SESSIONS_DIR):
            for filename in os.listdir(SESSIONS_DIR):
                if filename.endswith(".json"):
                    filepath = os.path.join(SESSIONS_DIR, filename)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            parsed = json.load(f)
                            sessions.append({
                                "session_id": parsed.get("session_id", filename.replace(".json", "")),
                                "saved_at": parsed.get("saved_at"),
                                "cookie_count": parsed.get("cookie_count", 0),
                                "source": "local",
                            })
                    except Exception:
                        pass
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """Delete a saved session from local storage."""
        filepath = os.path.join(SESSIONS_DIR, f"{session_id}.json")
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"🗑️ [SESSION STORE]: Deleted session '{session_id}' from local storage.")
            return True
        return False

    def _save_local(self, session_id: str, serialized: str) -> None:
        """Save session data to a local JSON file."""
        filepath = os.path.join(SESSIONS_DIR, f"{session_id}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(serialized)
        logger.info(f"✅ [SESSION STORE]: Saved session '{session_id}' to {filepath}")

    def _load_session(self, session_id: str) -> Optional[dict]:
        """Load session data from a local JSON file."""
        filepath = os.path.join(SESSIONS_DIR, f"{session_id}.json")
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"❌ [SESSION STORE]: Failed to read local session file: {e}")
        return None
