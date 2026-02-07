import asyncio
import shutil
from pathlib import Path
from dataclasses import dataclass
from typing import Any, List, Optional, Callable

# Mocking the service dependencies and models
@dataclass
class MockUploadFile:
    filename: str
    content: bytes

    async def read(self):
        return self.content

@dataclass(frozen=True)
class StudentSubmitDeps:
    uploads_dir: Path
    app_root: Path
    student_submissions_dir: Path
    run_script: Callable[[List[str]], str]
    sanitize_filename: Callable[[str], str]

import sys
import os

# Adjust path to include project root
sys.path.append(os.getcwd())

async def reproduce_vulnerability():
    print("--- Verifying Fix for Path Traversal in Student Submit ---")
    
    # Setup directories
    base_dir = Path("./tmp_repro_submit_verify")
    if base_dir.exists():
        shutil.rmtree(base_dir)
    base_dir.mkdir()
    
    uploads_dir = base_dir / "uploads"
    submissions_dir = base_dir / "submissions"
    app_root = base_dir / "app"
    app_root.mkdir()
    
    # Target file to overwrite (simulation)
    target_file = base_dir / "target.txt"
    target_file.write_text("original content")
    
    # Malicious filename
    malicious_filename = "../target.txt"
    
    mock_file = MockUploadFile(filename=malicious_filename, content=b"hacked content")
    
    def sanitize_filename(name: str) -> str:
        return Path(name).name

    deps = StudentSubmitDeps(
        uploads_dir=uploads_dir,
        app_root=app_root,
        student_submissions_dir=submissions_dir,
        run_script=lambda args: "mock output",
        sanitize_filename=sanitize_filename
    )
    
    print(f"Initial target file content: {target_file.read_text()}")
    
    try:
        from services.api.student_submit_service import submit
        await submit(
            student_id="student1",
            files=[mock_file],
            assignment_id="assign1",
            auto_assignment=False,
            deps=deps
        )
        
        # Check if target file is modified
        if target_file.read_text() == "original content":
             print("[SUCCESS] Vulnerability Fixed: Target file was NOT overwritten.")
             
             # Check if the file was saved securely (sanitized)
             sanitized_path = uploads_dir / "target.txt"
             if sanitized_path.exists():
                 print(f"[INFO] File saved correctly at: {sanitized_path}")
             else:
                 print("[WARN] File not found in uploads dir (maybe logic error?)")
                 print("Listing uploads dir:")
                 for f in uploads_dir.glob("**/*"):
                     print(f)
        else:
            print("[CRITICAL] Vulnerability STILL EXISTS: Target file was overwritten!")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Cleanup
        if base_dir.exists():
            shutil.rmtree(base_dir)

if __name__ == "__main__":
    asyncio.run(reproduce_vulnerability())