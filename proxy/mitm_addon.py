from mitmproxy import http
from loguru import logger
import re

class EvasionAddon:
    """
    mitmproxy addon to programmatically block tracking scripts, rewrite headers,
    and inject custom logic to evade bot detection.
    """
    def __init__(self):
        # List of regex patterns for known tracking/profiling domains
        self.block_patterns = [
            re.compile(r"google-analytics\.com"),
            re.compile(r"datadome\.co"),
            re.compile(r"sentry\.io"),
            re.compile(r"doubleclick\.net"),
            re.compile(r"facebook\.net/en_US/fbevents\.js")
        ]
        logger.info("🛡️ [MITM] EvasionAddon initialized with telemetry blocking.")

    def request(self, flow: http.HTTPFlow):
        url = flow.request.pretty_url
        
        # 1. Block heavy tracking & profiling scripts before they reach the browser canvas
        if any(pattern.search(url) for pattern in self.block_patterns):
            logger.info(f"🚫 [MITM] Blocked telemetry request: {url}")
            flow.kill()
            return
            
        # 2. Rewrite Headers (e.g., strip Playwright specific headers if any slipped through)
        if "playwright" in flow.request.headers.get("User-Agent", "").lower():
            logger.warning("⚠️ [MITM] Detected Playwright UA, stripping it.")
            flow.request.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            
        # 3. Dynamic header injection (Example: Removing WebRTC tracking headers)
        if "x-webrtc-ip" in flow.request.headers:
            del flow.request.headers["x-webrtc-ip"]

addons = [
    EvasionAddon()
]
