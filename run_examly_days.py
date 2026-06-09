import subprocess
import sys
import time
import os

# Force utf-8 encoding for standard output just in case
sys.stdout.reconfigure(encoding='utf-8')

def run_days():
    start_day = 1
    end_day = 10
    
    url = "https://mbu931.examly.io/login"
    
    for day in range(start_day, end_day + 1):
        task_str = f"Day {day}"
        print("="*50)
        print(f"[*] Starting Automation for: {task_str}")
        print("="*50)
        
        cmd = [
            sys.executable,
            "main.py",
            "--url", url,
            "--task", task_str
        ]
        
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        
        try:
            # We run without --headless so you can see the browser in action.
            subprocess.run(cmd, check=True, env=env)
            print(f"[+] Completed {task_str}")
        except subprocess.CalledProcessError as e:
            print(f"[-] Failed to complete {task_str}. Error: {e}")
            print("Moving to the next day...")
            
        print("Waiting 10 seconds before starting the next day...")
        time.sleep(10)
        
    print("[*] All done with days 1 through 10!")

if __name__ == "__main__":
    run_days()
