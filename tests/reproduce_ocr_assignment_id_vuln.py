
import asyncio
import shutil
from pathlib import Path
from dataclasses import dataclass
from typing import Any, List, Optional, Callable

@dataclass
class MockUploadFile:
    filename: str
    content: bytes

    async def read(self):
        return self.content

@dataclass(frozen=True)
class AssignmentQuestionsOcrDeps:
    uploads_dir: Path
    app_root: Path
    run_script: Callable[[List[str]], str]
    sanitize_filename: Callable[[str], str]

import sys
import os
sys.path.append(os.getcwd())

async def reproduce_assignment_id_vuln():
    print("--- Verifying Path Traversal via assignment_id in OCR ---")
    
    base_dir = Path("./tmp_repro_ocr_assign_id")
    if base_dir.exists():
        shutil.rmtree(base_dir)
    base_dir.mkdir()
    
    uploads_dir = base_dir / "uploads"
    app_root = base_dir / "app"
    app_root.mkdir()
    
    # Target file to overwrite: base_dir/target.txt
    # uploads_dir / "assignment_ocr" / assignment_id / filename
    # assignment_id = "../../.."
    # path = .../uploads/assignment_ocr/../../../filename -> .../base_dir/filename
    
    target_file = base_dir / "target.txt"
    target_file.write_text("original content")
    
    # Filename is sanitized (from previous fix), so we use a safe filename "target.txt"
    safe_filename = "target.txt"
    
    # Malicious assignment_id
    malicious_assignment_id = "../../.."
    
    mock_file = MockUploadFile(filename=safe_filename, content=b"hacked content")
    
    def sanitize_filename(name: str) -> str:
        return Path(name).name

    deps = AssignmentQuestionsOcrDeps(
        uploads_dir=uploads_dir,
        app_root=app_root,
        run_script=lambda args: "mock output",
        sanitize_filename=sanitize_filename
    )
    
    try:
        from services.api.assignment_questions_ocr_service import assignment_questions_ocr
        await assignment_questions_ocr(
            assignment_id=malicious_assignment_id,
            files=[mock_file],
            kp_id=None,
            difficulty=None,
            tags=None,
            ocr_mode=None,
            language=None,
            deps=deps
        )
        
        # Check if target file is modified
        # It should be at base_dir / "target.txt" if traversal worked
        if target_file.read_text() == "hacked content":
             print("[CRITICAL] Vulnerability Reproduced: Target file was overwritten via assignment_id!")
        else:
             print("[INFO] Target file content unchanged (or path logic prevented it).")
             # Debug where it went
             print("Listing base dir:")
             for f in base_dir.glob("**/*"):
                 print(f)

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if base_dir.exists():
             shutil.rmtree(base_dir)

if __name__ == "__main__":
    asyncio.run(reproduce_assignment_id_vuln())
