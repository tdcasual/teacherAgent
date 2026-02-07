import io
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.student_ops_api_service import (
    StudentOpsApiDeps,
    update_profile,
    upload_files,
    verify_student,
)


class _Upload:
    def __init__(self, name: str, data: bytes):
        self.filename = name
        self.file = io.BytesIO(data)


class StudentOpsApiServiceTest(unittest.TestCase):
    def test_verify_student_missing_and_multiple(self):
        logs = []
        deps = StudentOpsApiDeps(
            uploads_dir=Path("/tmp"),
            app_root=Path("/tmp/app"),
            sanitize_filename=lambda s: s,
            save_upload_file=lambda _f, _p: None,  # type: ignore[arg-type]
            run_script=lambda _args: "",
            student_candidates_by_name=lambda _name: [{"student_id": "S1", "class_name": "高二2401班"}, {"student_id": "S2", "class_name": "高二2402班"}],
            normalize=lambda s: "".join(str(s).split()).lower(),
            diag_log=lambda event, payload=None: logs.append((event, payload or {})),
        )
        missing = verify_student("", "", deps=deps)
        self.assertEqual(missing.get("error"), "missing_name")

        multiple = verify_student("张三", "", deps=deps)
        self.assertEqual(multiple.get("error"), "multiple")
        self.assertEqual(logs[-1][0], "student.verify.multiple")

    def test_update_profile_builds_script_args(self):
        captured = {}
        deps = StudentOpsApiDeps(
            uploads_dir=Path("/tmp"),
            app_root=Path("/tmp/app"),
            sanitize_filename=lambda s: s,
            save_upload_file=lambda _f, _p: None,  # type: ignore[arg-type]
            run_script=lambda args: captured.setdefault("args", list(args)) or "ok",
            student_candidates_by_name=lambda _name: [],
            normalize=lambda s: str(s),
            diag_log=lambda _e, _p=None: None,
        )
        payload = update_profile(
            student_id="S1",
            weak_kp="力学",
            strong_kp="电学",
            medium_kp="热学",
            next_focus="受力分析",
            interaction_note="课堂表现不错",
            deps=deps,
        )
        args = captured.get("args") or []
        self.assertIn("--student-id", args)
        self.assertIn("S1", args)
        self.assertTrue(payload.get("ok"))

    def test_upload_files_saves_sanitized_names(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            async def _save(upload, dest):  # type: ignore[no-untyped-def]
                dest.write_bytes(upload.file.read())
                return len(dest.read_bytes())

            deps = StudentOpsApiDeps(
                uploads_dir=root,
                app_root=Path(td),
                sanitize_filename=lambda s: "" if s.startswith(".") else s,
                save_upload_file=_save,
                run_script=lambda _args: "",
                student_candidates_by_name=lambda _name: [],
                normalize=lambda s: str(s),
                diag_log=lambda _e, _p=None: None,
            )

            async def _run():
                return await upload_files(
                    [_Upload("a.txt", b"1"), _Upload(".DS_Store", b"x"), _Upload("b.txt", b"2")],
                    deps=deps,
                )

            import asyncio

            out = asyncio.run(_run())
            self.assertEqual(len(out.get("saved") or []), 2)


if __name__ == "__main__":
    unittest.main()
