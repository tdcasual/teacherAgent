from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatAttachmentRef(BaseModel):
    attachment_id: str


class ChatAnalysisTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_type: str
    target_id: str
    source_domain: Optional[str] = None
    artifact_type: Optional[str] = None
    report_id: Optional[str] = None
    strategy_id: Optional[str] = None
    teacher_id: Optional[str] = None

    @field_validator("target_type", "target_id")
    @classmethod
    def _require_non_empty(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("analysis target field is required")
        return normalized

    @model_validator(mode="after")
    def _normalize_report_metadata(self) -> 'ChatAnalysisTarget':
        self.source_domain = str(self.source_domain or '').strip() or None
        self.artifact_type = str(self.artifact_type or '').strip() or None
        self.strategy_id = str(self.strategy_id or '').strip() or None
        self.teacher_id = str(self.teacher_id or '').strip() or None
        report_id = str(self.report_id or '').strip()
        if self.target_type == 'report' and not report_id:
            report_id = self.target_id
        self.report_id = report_id or None
        return self


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: List[ChatMessage]
    role: Optional[str] = None
    skill_id: Optional[str] = None
    teacher_id: Optional[str] = None
    student_id: Optional[str] = None
    assignment_id: Optional[str] = None
    assignment_date: Optional[str] = None
    attachments: Optional[List[ChatAttachmentRef]] = None
    attachment_context: Optional[str] = None
    # Deprecated: accepted so extra=forbid clients still 200; ignored by runtime.
    analysis_target: Optional[ChatAnalysisTarget] = None


class ChatStartRequest(ChatRequest):
    request_id: str
    session_id: Optional[str] = None


class TeacherMemoryProposalReviewRequest(BaseModel):
    teacher_id: Optional[str] = None
    approve: bool = True


class TeacherToolConfirmRequest(BaseModel):
    confirm_id: str
    confirmed: bool = True


class StudentMemoryProposalCreateRequest(BaseModel):
    teacher_id: Optional[str] = None
    student_id: str
    memory_type: str
    content: str
    evidence_refs: Optional[List[str]] = None
    source: Optional[str] = None


class StudentMemoryProposalReviewRequest(BaseModel):
    teacher_id: Optional[str] = None
    approve: bool = True


class StudentImportRequest(BaseModel):
    source: Optional[str] = None
    file_path: Optional[str] = None
    mode: Optional[str] = None


class AssignmentRequirementsRequest(BaseModel):
    assignment_id: str
    date: Optional[str] = None
    requirements: Dict[str, Any]
    created_by: Optional[str] = None


class TeacherGradeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    override_score: Optional[float] = None
    override_score_earned: Optional[float] = None
    comment: Optional[str] = None
    adopted_coach_excerpts: Optional[List[Dict[str, Any]]] = None
    attempt_id: Optional[str] = None


class StudentVerifyRequest(BaseModel):
    name: str
    class_name: Optional[str] = None


class StudentIdentifyRequest(BaseModel):
    name: str
    class_name: Optional[str] = None


class StudentLoginRequest(BaseModel):
    candidate_id: str
    credential_type: str
    credential: str


class StudentSetPasswordRequest(BaseModel):
    candidate_id: str
    credential_type: str
    credential: str
    new_password: str


class TeacherIdentifyRequest(BaseModel):
    name: str
    email: Optional[str] = None


class TeacherLoginRequest(BaseModel):
    candidate_id: str
    credential_type: str
    credential: str


class TeacherSetPasswordRequest(BaseModel):
    candidate_id: str
    credential_type: str
    credential: str
    new_password: str


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AuthResetTokenRequest(BaseModel):
    target_id: str


class AuthExportTokensRequest(BaseModel):
    ids: Optional[List[str]] = None


class AdminTeacherCreateRequest(BaseModel):
    teacher_name: str
    email: Optional[str] = None
    teacher_id: Optional[str] = None


class AdminTeacherSetDisabledRequest(BaseModel):
    target_id: str
    is_disabled: bool


class AdminTeacherResetPasswordRequest(BaseModel):
    target_id: str
    new_password: Optional[str] = None


class TeacherStudentPasswordResetRequest(BaseModel):
    scope: str = "student"
    student_id: Optional[str] = None
    class_name: Optional[str] = None
    new_password: Optional[str] = None


class AdminSubjectAddRequest(BaseModel):
    subject_id: str
    display_name: str
    pack_id: Optional[str] = None


class AdminRosterRequest(BaseModel):
    teacher_id: str
    subject_id: str
    class_name: str
    allow_empty: bool = False


class AdminEnrollClassRequest(BaseModel):
    teacher_id: str
    subject_id: str
    class_name: str
    resync: bool = False


class AdminEnrollRequest(BaseModel):
    student_id: str
    subject_id: str
    class_name: str
    teacher_id: Optional[str] = None


class AdminUnenrollRequest(BaseModel):
    student_id: str
    subject_id: str
    class_name: str


class AdminBulkMoveRequest(BaseModel):
    subject_id: str
    from_class: str
    to_class: str
    student_ids: Optional[List[str]] = None


class AdminRenameClassRequest(BaseModel):
    subject_id: str
    old_class_name: str
    new_class_name: str


class AdminAssignmentClaimRequest(BaseModel):
    teacher_id: str
    subject_id: str
    visibility_status: Optional[str] = "draft"


class UploadConfirmRequest(BaseModel):
    job_id: str
    requirements_override: Optional[Dict[str, Any]] = None
    confirm: Optional[bool] = True
    strict_requirements: Optional[bool] = True


class UploadDraftSaveRequest(BaseModel):
    job_id: str
    requirements: Optional[Dict[str, Any]] = None
    questions: Optional[List[Dict[str, Any]]] = None


class TeacherProviderRegistryCreateRequest(BaseModel):
    teacher_id: Optional[str] = None
    provider_id: Optional[str] = None
    display_name: Optional[str] = None
    base_url: str
    api_key: str
    default_model: Optional[str] = None
    enabled: Optional[bool] = True


class TeacherProviderRegistryUpdateRequest(BaseModel):
    teacher_id: Optional[str] = None
    display_name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    default_model: Optional[str] = None
    enabled: Optional[bool] = None


class TeacherProviderRegistryDeleteRequest(BaseModel):
    teacher_id: Optional[str] = None


class TeacherProviderRegistryProbeRequest(BaseModel):
    teacher_id: Optional[str] = None


class TeacherModelConfigUpdateRequest(BaseModel):
    teacher_id: Optional[str] = None
    models: Dict[str, Any]


class ChatResponse(BaseModel):
    reply: str
    role: Optional[str] = None

