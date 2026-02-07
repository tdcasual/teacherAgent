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
class AssignmentQuestionsOcrDeps:
    uploads_dir: Path
    app_root: Path
    run_script: Callable[[List[str]], str]
    sanitize_filename: Callable[[str], str]

import sys
import os

# Adjust path to include project root
sys.path.append(os.getcwd())

async def reproduce_ocr_vulnerability():
    print("--- Verifying Fix for Path Traversal in Assignment OCR ---")
    
    # Setup directories
    base_dir = Path("./tmp_repro_ocr_verify")
    if base_dir.exists():
        shutil.rmtree(base_dir)
    base_dir.mkdir()
    
    uploads_dir = base_dir / "uploads"
    app_root = base_dir / "app"
    app_root.mkdir()
    
    # Target file to overwrite (simulation)
    target_file = base_dir / "target.txt"
    target_file.write_text("original content")
    
    # Malicious filename
    malicious_filename = "../../../target.txt"
    
    mock_file = MockUploadFile(filename=malicious_filename, content=b"hacked content")
    
    def sanitize_filename(name: str) -> str:
        return Path(name).name

    deps = AssignmentQuestionsOcrDeps(
        uploads_dir=uploads_dir,
        app_root=app_root,
        run_script=lambda args: "mock output",
        sanitize_filename=sanitize_filename
    )
    
    print(f"Initial target file content: {target_file.read_text()}")
    
    try:
        from services.api.assignment_questions_ocr_service import assignment_questions_ocr
        await assignment_questions_ocr(
            assignment_id="assign1",
            files=[mock_file],
            kp_id=None,
            difficulty=None,
            tags=None,
            ocr_mode=None,
            language=None,
            deps=deps
        )
        
        # Check if target file is modified
        if target_file.read_text() == "original content":
             print("[SUCCESS] Vulnerability Fixed: Target file was NOT overwritten.")
        else:
            print("[CRITICAL] Vulnerability STILL EXISTS: Target file was overwritten!")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Cleanup
        if base_dir.exists():
            shutil.rmtree(base_dir)

if __name__ == "__main__":
    asyncio.run(reproduce_ocr_vulnerability())