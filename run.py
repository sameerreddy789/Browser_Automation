"""
run.py — Convenience Launcher

Starts all services needed for the full browser agent stack:
1. PocketBase (database for HITL dashboard)
2. Streamlit dashboard (browser-based monitoring UI)
3. The browser agent itself (main.py)

Usage:
    python run.py
    python run.py --url https://example.com --task "Do something"
    python run.py --no-dashboard    # Skip the Streamlit dashboard
    python run.py --no-pocketbase   # Skip PocketBase (HITL fallback to terminal)

All extra arguments are passed through to main.py.
"""

import atexit
import os
import platform
import subprocess
import sys
import time


# Track background processes for cleanup
_background_processes: list[subprocess.Popen] = []


def cleanup():
    """Terminate all background processes on exit."""
    for proc in _background_processes:
        try:
            if proc.poll() is None:  # Still running
                proc.terminate()
                proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    if _background_processes:
        print("\n🧹 All background services stopped.")


# Register cleanup for normal exit
atexit.register(cleanup)


def start_pocketbase() -> bool:
    """Start PocketBase if the binary exists."""
    project_root = os.path.dirname(os.path.abspath(__file__))
    pb_dir = os.path.join(project_root, "pocketbase")
    pb_data = os.path.join(project_root, "pb_data")
    
    if platform.system().lower() == "windows":
        pb_exe = os.path.join(pb_dir, "pocketbase.exe")
    else:
        pb_exe = os.path.join(pb_dir, "pocketbase")
    
    if not os.path.exists(pb_exe):
        print("ℹ️  PocketBase not found. Run 'python hitl/setup_pocketbase.py' to set it up.")
        print("   HITL will fall back to terminal input.\n")
        return False
    
    os.makedirs(pb_data, exist_ok=True)
    
    print("🚀 Starting PocketBase...")
    proc = subprocess.Popen(
        [pb_exe, "serve", f"--dir={pb_data}", "--http=127.0.0.1:8090"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _background_processes.append(proc)
    time.sleep(1.5)
    
    if proc.poll() is not None:
        print("⚠️  PocketBase failed to start. HITL will use terminal fallback.\n")
        return False
    
    print("✅ PocketBase running at http://127.0.0.1:8090\n")
    return True


def start_streamlit() -> bool:
    """Start the Streamlit HITL dashboard."""
    project_root = os.path.dirname(os.path.abspath(__file__))
    dashboard_path = os.path.join(project_root, "hitl", "dashboard.py")
    
    if not os.path.exists(dashboard_path):
        print("⚠️  Dashboard not found at hitl/dashboard.py\n")
        return False
    
    print("🚀 Starting Streamlit dashboard...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", dashboard_path, 
         "--server.headless=true", "--server.port=8501"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _background_processes.append(proc)
    time.sleep(2)
    
    if proc.poll() is not None:
        print("⚠️  Streamlit failed to start.\n")
        return False
    
    print("✅ Dashboard running at http://localhost:8501\n")
    return True


def main():
    print()
    print("=" * 60)
    print("  🤖 Browser Agent — Full Stack Launcher")
    print("=" * 60)
    print()
    
    # Parse our own flags (before passing the rest to main.py)
    skip_dashboard = "--no-dashboard" in sys.argv
    skip_pocketbase = "--no-pocketbase" in sys.argv
    
    # Remove our flags from argv before passing to main.py
    passthrough_args = [
        arg for arg in sys.argv[1:] 
        if arg not in ("--no-dashboard", "--no-pocketbase")
    ]
    
    # Step 1: Start PocketBase
    if not skip_pocketbase:
        start_pocketbase()
    else:
        print("⏭️  Skipping PocketBase (--no-pocketbase flag)\n")
    
    # Step 2: Start Streamlit dashboard
    if not skip_dashboard and not skip_pocketbase:
        start_streamlit()
    elif skip_dashboard:
        print("⏭️  Skipping Streamlit dashboard (--no-dashboard flag)\n")
    
    # Step 3: Run the main agent
    print("─" * 60)
    print("🤖 Starting Browser Agent...\n")
    
    project_root = os.path.dirname(os.path.abspath(__file__))
    main_script = os.path.join(project_root, "main.py")
    
    try:
        # Run main.py as a subprocess so we can capture Ctrl+C cleanly
        result = subprocess.run(
            [sys.executable, main_script] + passthrough_args,
            cwd=project_root,
        )
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        # cleanup() is called automatically via atexit


if __name__ == "__main__":
    main()
