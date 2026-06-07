"""
hitl/setup_pocketbase.py — PocketBase Auto-Setup Script

Downloads PocketBase (if not already present), starts it,
and creates the required 'bot_state' collection.

Run once before using the HITL dashboard:
    python hitl/setup_pocketbase.py

What it does:
1. Downloads the PocketBase binary for your OS into ./pocketbase/
2. Starts PocketBase on port 8090
3. Creates the 'bot_state' collection with the right schema
4. Keeps PocketBase running so the dashboard and agent can use it
"""

import os
import platform
import subprocess
import sys
import time
import zipfile
import json

# PocketBase version to download
PB_VERSION = "0.25.9"

# Where to store the PocketBase binary
PB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pocketbase")
PB_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pb_data")


def get_download_url() -> str:
    """Get the correct PocketBase download URL for the current OS/architecture."""
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    if system == "windows":
        if machine in ("amd64", "x86_64", "x64"):
            return f"https://github.com/pocketbase/pocketbase/releases/download/v{PB_VERSION}/pocketbase_{PB_VERSION}_windows_amd64.zip"
        else:
            return f"https://github.com/pocketbase/pocketbase/releases/download/v{PB_VERSION}/pocketbase_{PB_VERSION}_windows_arm64.zip"
    elif system == "linux":
        if machine in ("amd64", "x86_64", "x64"):
            return f"https://github.com/pocketbase/pocketbase/releases/download/v{PB_VERSION}/pocketbase_{PB_VERSION}_linux_amd64.zip"
        elif machine in ("aarch64", "arm64"):
            return f"https://github.com/pocketbase/pocketbase/releases/download/v{PB_VERSION}/pocketbase_{PB_VERSION}_linux_arm64.zip"
        else:
            return f"https://github.com/pocketbase/pocketbase/releases/download/v{PB_VERSION}/pocketbase_{PB_VERSION}_linux_amd64.zip"
    elif system == "darwin":
        if machine in ("arm64", "aarch64"):
            return f"https://github.com/pocketbase/pocketbase/releases/download/v{PB_VERSION}/pocketbase_{PB_VERSION}_darwin_arm64.zip"
        else:
            return f"https://github.com/pocketbase/pocketbase/releases/download/v{PB_VERSION}/pocketbase_{PB_VERSION}_darwin_amd64.zip"
    else:
        raise RuntimeError(f"Unsupported OS: {system}")


def get_pb_executable() -> str:
    """Get the path to the PocketBase executable."""
    system = platform.system().lower()
    if system == "windows":
        return os.path.join(PB_DIR, "pocketbase.exe")
    else:
        return os.path.join(PB_DIR, "pocketbase")


def download_pocketbase():
    """Download and extract PocketBase if not already present."""
    pb_exe = get_pb_executable()
    
    if os.path.exists(pb_exe):
        print(f"✅ PocketBase already exists at: {pb_exe}")
        return
    
    os.makedirs(PB_DIR, exist_ok=True)
    
    url = get_download_url()
    zip_path = os.path.join(PB_DIR, "pocketbase.zip")
    
    print(f"📥 Downloading PocketBase v{PB_VERSION}...")
    print(f"   URL: {url}")
    
    # Use urllib to avoid extra dependencies
    import urllib.request
    urllib.request.urlretrieve(url, zip_path)
    
    print("📦 Extracting...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(PB_DIR)
    
    # Make executable on Unix
    if platform.system().lower() != "windows":
        os.chmod(pb_exe, 0o755)
    
    # Clean up zip
    os.remove(zip_path)
    
    print(f"✅ PocketBase installed at: {pb_exe}")


def start_pocketbase() -> subprocess.Popen:
    """Start PocketBase as a background process."""
    pb_exe = get_pb_executable()
    
    if not os.path.exists(pb_exe):
        raise FileNotFoundError(f"PocketBase not found at {pb_exe}. Run download first.")
    
    os.makedirs(PB_DATA_DIR, exist_ok=True)
    
    print(f"🚀 Starting PocketBase (data dir: {PB_DATA_DIR})...")
    
    process = subprocess.Popen(
        [pb_exe, "serve", f"--dir={PB_DATA_DIR}", "--http=127.0.0.1:8090"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    
    # Wait a bit for it to start
    time.sleep(2)
    
    if process.poll() is not None:
        stderr = process.stderr.read().decode() if process.stderr else ""
        raise RuntimeError(f"PocketBase failed to start: {stderr}")
    
    print("✅ PocketBase is running at http://127.0.0.1:8090")
    print("   Admin UI: http://127.0.0.1:8090/_/")
    
    return process


def create_collection():
    """
    Create the 'bot_state' collection via PocketBase's API.
    
    Uses the PocketBase REST API directly since the Python SDK
    doesn't support collection management easily.
    """
    import urllib.request
    import urllib.error
    
    api_url = "http://127.0.0.1:8090/api/collections"
    
    # Check if collection already exists
    try:
        req = urllib.request.Request(f"{api_url}?filter=name='bot_state'")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            if data.get("items") and len(data["items"]) > 0:
                print("✅ 'bot_state' collection already exists.")
                return
    except urllib.error.HTTPError:
        pass  # Collection doesn't exist, proceed to create
    except Exception:
        pass
    
    # Create the collection
    collection_schema = {
        "name": "bot_state",
        "type": "base",
        "schema": [
            {
                "name": "state",
                "type": "text",
                "required": True,
                "options": {"maxSize": 50},
            },
            {
                "name": "message",
                "type": "text",
                "required": False,
                "options": {"maxSize": 5000},
            },
            {
                "name": "screenshot_b64",
                "type": "text",
                "required": False,
                "options": {"maxSize": 10000000},  # ~7.5MB base64 image
            },
            {
                "name": "user_response",
                "type": "text",
                "required": False,
                "options": {"maxSize": 5000},
            },
            {
                "name": "timestamp",
                "type": "number",
                "required": False,
            },
        ],
        "listRule": "",    # Public read access
        "viewRule": "",
        "createRule": "",  # Public write access (local only)
        "updateRule": "",
        "deleteRule": "",
    }
    
    try:
        data = json.dumps(collection_schema).encode("utf-8")
        req = urllib.request.Request(
            api_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            print("✅ Created 'bot_state' collection successfully.")
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        if "already exists" in body.lower() or e.code == 400:
            print("✅ 'bot_state' collection already exists.")
        else:
            print(f"⚠️ Could not create collection (HTTP {e.code}): {body}")
            print("   You may need to create it manually via the admin UI at http://127.0.0.1:8090/_/")
    except Exception as e:
        print(f"⚠️ Could not create collection: {e}")
        print("   You may need to create it manually via the admin UI at http://127.0.0.1:8090/_/")


def main():
    print("=" * 60)
    print("  🤖 PocketBase Setup for HITL Dashboard")
    print("=" * 60)
    print()
    
    # Step 1: Download PocketBase
    download_pocketbase()
    print()
    
    # Step 2: Start PocketBase
    try:
        process = start_pocketbase()
    except Exception as e:
        print(f"❌ {e}")
        sys.exit(1)
    
    print()
    
    # Step 3: Create the collection
    create_collection()
    
    print()
    print("=" * 60)
    print("  ✅ Setup complete!")
    print()
    print("  PocketBase is running at: http://127.0.0.1:8090")
    print("  Admin UI: http://127.0.0.1:8090/_/")
    print()
    print("  You can now:")
    print("  1. Start the dashboard:  streamlit run hitl/dashboard.py")
    print("  2. Run the agent:        python main.py")
    print()
    print("  Press Ctrl+C to stop PocketBase.")
    print("=" * 60)
    
    # Keep running until Ctrl+C
    try:
        process.wait()
    except KeyboardInterrupt:
        print("\n🛑 Stopping PocketBase...")
        process.terminate()
        process.wait()
        print("✅ PocketBase stopped.")


if __name__ == "__main__":
    main()
