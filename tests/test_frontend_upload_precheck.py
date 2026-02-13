from pathlib import Path


_ROOT = Path(__file__).resolve().parent.parent


def _read(rel_path: str) -> str:
    return (_ROOT / rel_path).read_text(encoding="utf-8")


def test_shared_upload_validation_declares_avatar_assignment_and_chat_limits() -> None:
    source = _read("frontend/apps/shared/uploadValidation.ts")
    assert "CHAT_ATTACHMENT_MAX_FILE_BYTES" in source
    assert "ASSIGNMENT_UPLOAD_MAX_TOTAL_BYTES" in source
    assert "AVATAR_MAX_FILE_BYTES" in source
    assert "validateFilesBeforeUpload" in source
    assert "validateAvatarFileBeforeUpload" in source


def test_chat_attachments_use_precheck_for_suffix_and_single_file_size() -> None:
    source = _read("frontend/apps/shared/useChatAttachments.ts")
    assert "validateFilesBeforeUpload(selected" in source
    assert "CHAT_ATTACHMENT_ALLOWED_SUFFIXES" in source
    assert "CHAT_ATTACHMENT_MAX_FILE_BYTES" in source


def test_assignment_workflow_uses_client_side_upload_precheck() -> None:
    source = _read("frontend/apps/teacher/src/features/workbench/hooks/useAssignmentWorkflow.ts")
    assert "ASSIGNMENT_UPLOAD_MAX_FILES_PER_FIELD" in source
    assert "ASSIGNMENT_UPLOAD_MAX_TOTAL_BYTES" in source
    assert "validateFilesBeforeUpload(uploadFiles" in source
    assert "validateFilesBeforeUpload(uploadAnswerFiles" in source


def test_persona_avatar_upload_uses_client_side_precheck() -> None:
    teacher_source = _read("frontend/apps/teacher/src/features/persona/TeacherPersonaManager.tsx")
    student_source = _read("frontend/apps/student/src/features/layout/StudentTopbar.tsx")
    assert "validateAvatarFileBeforeUpload" in teacher_source
    assert "validateAvatarFileBeforeUpload" in student_source
