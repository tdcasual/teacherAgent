from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatAttachmentRef(BaseModel):
    attachment_id: str


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: List[ChatMessage]
    role: Optional[str] = None
    skill_id: Optional[str] = None
    teacher_id: Optional[str] = None
    student_id: Optional[str] = None
    assignment_id: Optional[str] = None
    assignment_date: Optional[str] = None
    auto_generate_assignment: Optional[bool] = None
    attachments: Optional[List[ChatAttachmentRef]] = None
    attachment_context: Optional[str] = None


class ChatStartRequest(ChatRequest):
    request_id: str
    session_id: Optional[str] = None


class TeacherMemoryProposalReviewRequest(BaseModel):
    teacher_id: Optional[str] = None
    approve: bool = True


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
    exam_id: Optional[str] = None
    file_path: Optional[str] = None
    mode: Optional[str] = None


class AssignmentRequirementsRequest(BaseModel):
    assignment_id: str
    date: Optional[str] = None
    requirements: Dict[str, Any]
    created_by: Optional[str] = None


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


class UploadConfirmRequest(BaseModel):
    job_id: str
    requirements_override: Optional[Dict[str, Any]] = None
    confirm: Optional[bool] = True
    strict_requirements: Optional[bool] = True


class UploadDraftSaveRequest(BaseModel):
    job_id: str
    requirements: Optional[Dict[str, Any]] = None
    questions: Optional[List[Dict[str, Any]]] = None


class ExamUploadConfirmRequest(BaseModel):
    job_id: str
    confirm: Optional[bool] = True


class ExamUploadDraftSaveRequest(BaseModel):
    job_id: str
    meta: Optional[Dict[str, Any]] = None
    questions: Optional[List[Dict[str, Any]]] = None
    score_schema: Optional[Dict[str, Any]] = None
    answer_key_text: Optional[str] = None
    reparse: Optional[bool] = False


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


class SurveyWebhookAckResponse(BaseModel):
    ok: bool = True
    job_id: str
    status: str
    accepted_at: Optional[str] = None


class SurveyReportSummary(BaseModel):
    report_id: str
    teacher_id: str
    class_name: Optional[str] = None
    status: str
    confidence: Optional[float] = None
    summary: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SurveyReportDetail(BaseModel):
    report: SurveyReportSummary
    analysis_artifact: Dict[str, Any]
    bundle_meta: Dict[str, Any]
    review_required: bool = False


class SurveyReportRerunRequest(BaseModel):
    teacher_id: Optional[str] = None
    reason: Optional[str] = None


class AnalysisReportRerunRequest(BaseModel):
    teacher_id: str
    domain: Optional[str] = None
    reason: Optional[str] = None


class SurveyReviewQueueItemSummary(BaseModel):
    report_id: str
    teacher_id: str
    reason: str
    confidence: Optional[float] = None
    created_at: Optional[str] = None
