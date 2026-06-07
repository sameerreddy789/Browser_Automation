# 🛠️ Python-Only Browser Automation Architecture Plan

This document outlines how to integrate all five major automation components—**Fingerprinting**, **Visual Grounding**, **Human-in-the-Loop (HITL)**, **Persistent Sessions**, and **Proxy Management**—into your project using **Python only**.

---

## 🗺️ Architectural Overview

```mermaid
graph TD
    A[main.py: Browser Agent] --> B[1. Anti-Bot & Fingerprinting]
    A --> C[2. Visual Grounding]
    A --> D[3. HITL Fallback Dashboard]
    A --> E[4. Session Storage]
    A --> F[5. Proxy Rotation]

    subgraph "1. Fingerprinting"
        B1[playwright-stealth]
        B2[curl_cffi / tls-client]
    end

    subgraph "2. Visual Grounding"
        C1[browser-use Vision Mode]
        C2[Custom Gemini coordinate detector]
    end

    subgraph "3. HITL Fallback"
        D1[PocketBase Python SDK]
        D2[Streamlit Live Screen Stream]
    end

    subgraph "4. Session Storage"
        E1[Playwright Persistent Context]
        E2[Redis-py Cookie Sync]
    end

    subgraph "5. Proxy Rotation"
        F1[mitmproxy Python scripts]
    end
```

---

## 📦 Python Dependencies to Add

To support all these features, we will add these libraries to our `pyproject.toml`:

```toml
dependencies = [
    # Existing dependencies
    "browser-use>=0.12.9",
    "langchain-google-genai>=4.2.4",
    "playwright>=1.60.0",
    "python-dotenv>=1.2.2",
    "python-ghost-cursor>=0.1.1",
    
    # Anti-detection & Fingerprinting
    "playwright-stealth>=1.0.6",
    "curl-cffi>=0.7.4",
    "tls-client>=1.0.1",

    # HITL & Database Sync
    "pocketbase>=0.18.0",
    "streamlit>=1.35.0",

    # Session & Proxy management
    "redis>=5.0.4",
    "mitmproxy>=10.3.0",
]
```

---

## 🚀 1. TLS & HTTP Fingerprinting (Python Only)

### The Problem
Cloudflare and Akamai detect default Playwright browsers using browser variables (`navigator.webdriver` is true) and TLS/HTTP2 fingerprints (which look like scripts, not real browsers).

### The Python Solution
1. **`playwright-stealth`**: A Python package that injects Javascript stealth scripts into Playwright before each page loads to hide automated variables.
2. **`curl_cffi` & `tls-client`**: When we need to scrape data directly without a browser, we use these Python libraries to perform HTTP requests that mimic a Chrome browser's TLS handshake and JA3/JA4 fingerprint.

```python
# Blueprint: playwright-stealth integration
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

async def launch_stealth_browser():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Injects stealth scripts
        await stealth_async(page)
        
        await page.goto("https://bot.sannysoft.com/")
```

---

## 🎨 2. Multimodal Visual Grounding (Python Only)

### The Problem
Traditional bots break when website CSS/HTML layouts change. Visual grounding lets the bot "see" the page like a human and click based on coordinates.

### The Python Solution
1. **`browser-use` Vision Mode**: Configure `browser-use` to send periodic screenshots to Gemini so it makes decisions visually.
2. **Custom coordinate detector**: If `browser-use` gets stuck, take a screenshot of the page, send it to Gemini with a request like *"find the Login button and return its X, Y coordinates as percentages"*, then click those coordinates.

```python
# Blueprint: Visual coordinate clicking with Gemini
import base64
from google import genai
from playwright.async_api import Page

async def click_element_visually(page: Page, element_description: str):
    # Take screenshot of viewport
    screenshot_bytes = await page.screenshot(type="png")
    screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
    
    # Ask Gemini for coordinates (0 to 1000 scale)
    client = genai.Client()
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[
            f"Locate the {element_description} in this image. Return the coordinates of its center as [x_percent, y_percent] from 0 to 100.",
            {"mime_type": "image/png", "data": screenshot_b64}
        ]
    )
    
    # Parse coordinates and scale to viewport size
    viewport = page.viewport_size
    # ... parse x, y percentages ...
    # await page.mouse.click(x_coordinate, y_coordinate)
```

---

## 🤝 3. Human-in-the-Loop Fallback (Python Only)

### The Problem
When the bot encounters a complex 3D CAPTCHA or gets completely stuck, it needs a way to pause, alert you, and let you take over or guide it.

### The Python Solution
1. **`PocketBase` + Python SDK**: PocketBase is a single-file database. We run it locally. When the bot gets stuck, it uploads a screenshot and sets status to `"PAUSED_FOR_USER"` in PocketBase.
2. **`Streamlit` Dashboard**: A lightweight Python web app that runs locally. It reads PocketBase, displays the bot's live screenshot, and displays a text box / buttons so you can type the answer or click "Resume".

```python
# Blueprint: Streamlit HITL Dashboard snippet
import streamlit as st
from pocketbase import PocketBase

pb = PocketBase("http://127.0.0.1:8090")

st.title("🤖 Bot Monitor & HITL Fallback")
bot_status = pb.collection("bot_state").get_first_list_item("")

if bot_status.state == "PAUSED_FOR_USER":
    st.warning("⚠️ Bot requires assistance!")
    st.image(bot_status.screenshot_url)
    user_input = st.text_input("Provide instruction or captcha solution:")
    if st.button("Submit & Resume"):
        pb.collection("bot_state").update(bot_status.id, {
            "state": "RUNNING",
            "user_response": user_input
        })
```

---

## 💾 4. Persistent Session Storage (Python Only)

### The Problem
We want to save cookies, session tokens, and local storage variables so the bot stays logged in across multiple runs.

### The Python Solution
1. **`launch_persistent_context`**: Save browser state to a local directory (we use `./agent_profile`).
2. **`redis-py` (Optional / Cloud Sync):** If you run your bot in multiple locations, we write a Python script to extract cookies from Playwright, serialize them, and store/encrypt them in a local Redis database.

```python
# Blueprint: Extracting cookies to Redis
import json
import redis
from playwright.async_api import BrowserContext

r = redis.Redis(host='localhost', port=6379, db=0)

async def backup_cookies_to_redis(context: BrowserContext, session_id: str):
    cookies = await context.cookies()
    # Serialize and store encrypted
    r.set(f"session:{session_id}:cookies", json.dumps(cookies), ex=86400) # 1 day expiry
```

---

## 🔀 5. Distributed Proxy Management (Python Only)

### The Problem
Websites block IPs if too many requests come from a single home or server IP address.

### The Python Solution
* **`mitmproxy` add-on**: Mitmproxy is built entirely in Python. We can run a small local mitmproxy background process with a custom Python script that intercepts all outgoing Playwright requests and routes them through a pool of proxies.

```python
# Blueprint: mitmproxy addon script (rotate_proxy.py)
import random

PROXIES = [
    "http://user:pass@proxy1.com:8000",
    "http://user:pass@proxy2.com:8000",
]

def request(flow):
    # Rotate proxy for every outgoing request automatically
    proxy = random.choice(PROXIES)
    flow.live.change_upstream_proxy_server(proxy)
```

---

## 📅 Step-by-Step Implementation Roadmap

If we implement these, we should do them in this order:

1. **Step 1: Anti-Bot & Fingerprinting Setup** (Install `playwright-stealth` and test against bot check websites).
2. **Step 2: Streamlit + PocketBase Dashboard** (Set up local PocketBase, run Streamlit dashboard to show screenshot & handle user manual inputs).
3. **Step 3: Vision Coordinate Grounding** (Write a helper script using Gemini API to click buttons visually).
4. **Step 4: Proxy Rotator using Mitmproxy** (Route Playwright through a local Python proxy injector).
5. **Step 5: Redis Session Storage** (Back up and restore session states).
