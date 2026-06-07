"""
hitl/dashboard.py — Streamlit HITL Dashboard

A local web dashboard for monitoring and controlling the browser agent.
Shows the bot's live screenshot, current status, and lets you type
responses when the bot gets stuck.

Run with:
    streamlit run hitl/dashboard.py

Opens at http://localhost:8501 by default.
"""

import base64
import os
import sys
import time

import streamlit as st

# Add project root to path so we can import project modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

# Page config — must be the first Streamlit command
st.set_page_config(
    page_title="🤖 Browser Agent — HITL Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS for a polished look ───────────────────────────────────────────
st.markdown("""
<style>
    /* Dark themed adjustments */
    .status-running { 
        color: #00c853; font-size: 1.4em; font-weight: bold; 
    }
    .status-paused { 
        color: #ff9100; font-size: 1.4em; font-weight: bold; 
        animation: pulse 1.5s infinite;
    }
    .status-error { 
        color: #ff1744; font-size: 1.4em; font-weight: bold; 
    }
    .status-completed { 
        color: #00b0ff; font-size: 1.4em; font-weight: bold; 
    }
    .status-idle { 
        color: #78909c; font-size: 1.4em; font-weight: bold; 
    }
    
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.5; }
        100% { opacity: 1; }
    }
    
    .metric-card {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 1em;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    .big-screenshot img {
        border-radius: 8px;
        border: 2px solid rgba(255, 255, 255, 0.1);
        max-width: 100%;
    }
</style>
""", unsafe_allow_html=True)


def get_pocketbase_client():
    """Connect to PocketBase and return client + record."""
    try:
        from pocketbase import PocketBase

        pb_url = os.getenv("POCKETBASE_URL", "http://127.0.0.1:8090")
        pb = PocketBase(pb_url)

        # Get the bot_state record
        records = pb.collection("bot_state").get_list(1, 1)
        if records.items:
            return pb, records.items[0]
        else:
            return pb, None
    except Exception as e:
        return None, None


def render_status_badge(state: str) -> str:
    """Return an HTML badge for the bot state."""
    css_class = {
        "RUNNING": "status-running",
        "PAUSED_FOR_USER": "status-paused",
        "ERROR": "status-error",
        "COMPLETED": "status-completed",
        "IDLE": "status-idle",
    }.get(state, "status-idle")
    
    icon = {
        "RUNNING": "🟢",
        "PAUSED_FOR_USER": "🟠",
        "ERROR": "🔴",
        "COMPLETED": "🔵",
        "IDLE": "⚪",
    }.get(state, "⚪")
    
    return f'<span class="{css_class}">{icon} {state}</span>'


# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🤖 Bot Controls")
    st.divider()
    
    auto_refresh = st.toggle("🔄 Auto-refresh", value=True, help="Automatically refresh the dashboard")
    refresh_interval = st.slider("Refresh interval (seconds)", 2, 30, 5)
    
    st.divider()
    st.caption("💡 The bot uploads screenshots here when it runs.")
    st.caption("When it gets stuck, type your response below the screenshot.")

# ── Main Content ─────────────────────────────────────────────────────────────
st.title("🤖 Browser Agent — HITL Dashboard")
st.caption("Monitor your browser agent and provide input when it needs help.")

# Connect to PocketBase
pb, record = get_pocketbase_client()

if pb is None:
    st.error(
        "❌ **Cannot connect to PocketBase.** \n\n"
        "Make sure PocketBase is running:\n"
        "```bash\n"
        "python hitl/setup_pocketbase.py\n"
        "```\n"
        "Or start it manually:\n"
        "```bash\n"
        "./pocketbase/pocketbase serve\n"
        "```"
    )
    st.stop()

if record is None:
    st.info("⏳ Waiting for the bot to start... No bot state found yet.")
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()
    st.stop()

# ── Display Bot State ────────────────────────────────────────────────────────
state = getattr(record, "state", "UNKNOWN")
message = getattr(record, "message", "")
screenshot_b64 = getattr(record, "screenshot_b64", "")
timestamp = getattr(record, "timestamp", 0)

# Status row
col1, col2, col3 = st.columns([2, 3, 2])

with col1:
    st.markdown("### Status")
    st.markdown(render_status_badge(state), unsafe_allow_html=True)

with col2:
    st.markdown("### Message")
    st.markdown(f"**{message}**" if message else "*No message*")

with col3:
    st.markdown("### Last Updated")
    if timestamp:
        elapsed = time.time() - float(timestamp)
        if elapsed < 60:
            st.markdown(f"**{elapsed:.0f}s ago**")
        else:
            st.markdown(f"**{elapsed / 60:.1f}m ago**")
    else:
        st.markdown("*Unknown*")

st.divider()

# ── Screenshot Display ───────────────────────────────────────────────────────
if screenshot_b64:
    st.markdown("### 📸 Live Screenshot")
    try:
        image_bytes = base64.b64decode(screenshot_b64)
        st.image(image_bytes, use_container_width=True)
    except Exception as e:
        st.warning(f"Could not decode screenshot: {e}")
else:
    st.info("📷 No screenshot available yet. The bot will upload one when it starts.")

# ── User Response Section (only when paused) ─────────────────────────────────
if state == "PAUSED_FOR_USER":
    st.divider()
    st.markdown("### ⚠️ Bot Needs Your Help!")
    st.warning(f"**Reason:** {message}")
    
    with st.form("user_response_form", clear_on_submit=True):
        user_input = st.text_area(
            "Your response (CAPTCHA solution, instruction, etc.):",
            placeholder="Type your response here...",
            height=100,
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            submit = st.form_submit_button("✅ Submit & Resume", type="primary", use_container_width=True)
        with col2:
            skip = st.form_submit_button("⏭️ Skip (Let bot continue)", use_container_width=True)
        
        if submit and user_input:
            try:
                pb.collection("bot_state").update(record.id, {
                    "state": "RUNNING",
                    "user_response": user_input,
                    "message": f"User responded: {user_input[:50]}...",
                    "timestamp": time.time(),
                })
                st.success("✅ Response sent! Bot will resume shortly.")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Failed to send response: {e}")
        
        if skip:
            try:
                pb.collection("bot_state").update(record.id, {
                    "state": "RUNNING",
                    "user_response": "__SKIP__",
                    "message": "User skipped — bot resuming",
                    "timestamp": time.time(),
                })
                st.info("⏭️ Skipped. Bot will try to continue on its own.")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Failed to skip: {e}")

# ── Emergency Controls ───────────────────────────────────────────────────────
with st.expander("🛑 Emergency Controls"):
    st.caption("Use these if the bot is misbehaving or you need to manually intervene.")
    
    ecol1, ecol2 = st.columns(2)
    
    with ecol1:
        if st.button("🛑 Force Stop Bot", type="secondary", use_container_width=True):
            try:
                pb.collection("bot_state").update(record.id, {
                    "state": "ERROR",
                    "message": "Force stopped by user via dashboard",
                    "user_response": "__FORCE_STOP__",
                    "timestamp": time.time(),
                })
                st.warning("Bot state set to ERROR. The bot should stop on its next check.")
            except Exception as e:
                st.error(f"Failed: {e}")
    
    with ecol2:
        if st.button("🔄 Reset to IDLE", type="secondary", use_container_width=True):
            try:
                pb.collection("bot_state").update(record.id, {
                    "state": "IDLE",
                    "message": "Reset by user",
                    "user_response": "",
                    "screenshot_b64": "",
                    "timestamp": time.time(),
                })
                st.info("Bot state reset to IDLE.")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")

# ── Auto-Refresh ─────────────────────────────────────────────────────────────
if auto_refresh:
    time.sleep(refresh_interval)
    st.rerun()
