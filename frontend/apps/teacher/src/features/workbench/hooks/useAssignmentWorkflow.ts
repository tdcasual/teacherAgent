import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import { buildAssignmentWorkflowIndicator } from '../workflowIndicators';
import {
  clampQuestionCount,
  computeLocalRequirementsMissing,
  isAssignmentKind,
  isContentSource,
  parseCommaList,
  parseLineList,
  formatMissingRequirements,
} from '../workbenchUtils';
import {
  safeLocalStorageGetItem,
  safeLocalStorageRemoveItem,
  safeLocalStorageSetItem,
} from '../../../utils/storage';
import { toUserFacingErrorMessage } from '../../../../../shared/errorMessage';
import {
  ASSIGNMENT_UPLOAD_ALLOWED_SUFFIXES,
  ASSIGNMENT_UPLOAD_MAX_FILE_BYTES,
  ASSIGNMENT_UPLOAD_MAX_FILES_PER_FIELD,
  ASSIGNMENT_UPLOAD_MAX_TOTAL_BYTES,
  validateFilesBeforeUpload,
} from '../../../../../shared/uploadValidation';
import type {
  AssignmentKind,
  AssignmentProgress,
  ContentSource,
  UploadDraft,
  UploadJobStatus,
  WorkflowIndicator,
  WorkflowStepState,
} from '../../../appTypes';
import type { PendingPickerChange } from '../../../types/workflow';

type UnknownRecord = Record<string, unknown>;

const toErrorMessage = (error: unknown, fallback = '请求失败') => {
  return toUserFacingErrorMessage(error, fallback);
};

// ---------------------------------------------------------------------------
// Params type – the state / setters the hook needs from the parent component
// ---------------------------------------------------------------------------

const toFolderDraft = (
  raw: Partial<UploadDraft> | null | undefined,
  fallback: {
    date: string;
    dueAt: string;
    scope: UploadDraft['scope'];
    className: string;
    studentIds: string;
    assignmentKind: AssignmentKind;
    contentSource: ContentSource;
  },
): UploadDraft => {
  const studentIds = Array.isArray(raw?.student_ids)
    ? raw.student_ids
    : parseCommaList(fallback.studentIds);
  return {
    assignment_id: String(raw?.assignment_id || ''),
    date: String(raw?.date || fallback.date || ''),
    due_at: String(raw?.due_at || fallback.dueAt || ''),
    scope: raw?.scope || fallback.scope,
    class_name: String(raw?.class_name || fallback.className || ''),
    student_ids: studentIds,
    questions: Array.isArray(raw?.questions) ? raw.questions : [],
    requirements: raw?.requirements || {},
    requirements_missing: Array.isArray(raw?.requirements_missing) ? raw.requirements_missing : [],
    assignment_kind: raw?.assignment_kind || fallback.assignmentKind,
    content_source: raw?.content_source || fallback.contentSource,
    question_count: raw?.question_count,
    draft_saved: raw?.draft_saved,
    delivery_mode: raw?.delivery_mode,
    warnings: raw?.warnings,
  };
};

interface UseAssignmentWorkflowParams {
  apiBase: string;

  assignmentKind: AssignmentKind;
  contentSource: ContentSource;
  completionRequiresSubmission: boolean;
  completionRequiresDiscussion: boolean;
  completionAllowPractice: boolean;
  setAssignmentKind: (value: AssignmentKind) => void;
  setContentSource: (value: ContentSource) => void;
  setCompletionRequiresSubmission: (value: boolean) => void;
  setCompletionRequiresDiscussion: (value: boolean) => void;
  setCompletionAllowPractice: (value: boolean) => void;

  // Upload card state
  uploadMode: string;
  uploadAssignmentId: string;
  uploadDate: string;
  uploadDueAt: string;
  uploadSubjectId: string;
  uploadScope: string;
  uploadClassName: string;
  uploadStudentIds: string;
  uploadFiles: File[];
  uploadAnswerFiles: File[];
  uploading: boolean;
  uploadStatus: string;
  uploadError: string;
  uploadCardCollapsed: boolean;
  uploadJobId: string;
  uploadJobInfo: UploadJobStatus | null;
  uploadConfirming: boolean;
  uploadStatusPollNonce: number;
  uploadDraft: UploadDraft | null;
  draftPanelCollapsed: boolean;
  draftLoading: boolean;
  draftError: string;
  questionShowCount: number;
  draftSaving: boolean;
  draftActionStatus: string;
  draftActionError: string;
  misconceptionsText: string;
  misconceptionsDirty: boolean;

  // Progress state
  progressPanelCollapsed: boolean;
  progressAssignmentId: string;
  progressLoading: boolean;
  progressError: string;
  progressData: AssignmentProgress | null;
  progressOnlyIncomplete: boolean;

  // Setters
  setUploadError: (value: string) => void;
  setUploadStatus: (value: string | ((prev: string) => string)) => void;
  setUploadJobId: (value: string) => void;
  setUploadJobInfo: (
    value: UploadJobStatus | null | ((prev: UploadJobStatus | null) => UploadJobStatus | null),
  ) => void;
  setUploadDraft: (
    value: UploadDraft | null | ((prev: UploadDraft | null) => UploadDraft | null),
  ) => void;
  setUploadFiles: (value: File[]) => void;
  setUploadAnswerFiles: (value: File[]) => void;
  setUploading: (value: boolean) => void;
  setUploadCardCollapsed: (value: boolean | ((prev: boolean) => boolean)) => void;
  setUploadConfirming: (value: boolean) => void;
  setUploadStatusPollNonce: (value: number | ((prev: number) => number)) => void;
  setDraftPanelCollapsed: (value: boolean | ((prev: boolean) => boolean)) => void;
  setDraftLoading: (value: boolean) => void;
  setDraftError: (value: string) => void;
  setQuestionShowCount: (value: number | ((prev: number) => number)) => void;
  setDraftSaving: (value: boolean) => void;
  setDraftActionStatus: (value: string) => void;
  setDraftActionError: (value: string) => void;
  setMisconceptionsText: (value: string) => void;
  setMisconceptionsDirty: (value: boolean) => void;
  setProgressPanelCollapsed: (value: boolean | ((prev: boolean) => boolean)) => void;
  setProgressAssignmentId: (value: string) => void;
  setProgressLoading: (value: boolean) => void;
  setProgressError: (value: string) => void;
  setProgressData: (value: AssignmentProgress | null) => void;
}

// ---------------------------------------------------------------------------
// Return type
// ---------------------------------------------------------------------------

interface UseAssignmentWorkflowReturn {
  handleUploadAssignment: (event: FormEvent) => Promise<void>;
  handleFromBank: (input: { kp: string; count: number }) => Promise<void>;
  handleGenerate: (input: {
    kp: string;
    perKp: number;
    topic: string;
    gradeLevel: string;
    seed: string;
  }) => Promise<void>;
  requestAssignmentKindChange: (kind: AssignmentKind) => void;
  requestContentSourceChange: (source: ContentSource) => void;
  pendingPickerChange: PendingPickerChange;
  confirmPendingPickerChange: () => void;
  cancelPendingPickerChange: () => void;
  saveDraft: (draft: UploadDraft) => Promise<void>;
  handleConfirmUpload: () => Promise<void>;
  fetchAssignmentProgress: (assignmentId?: string) => Promise<void>;
  archiveAssignment: (assignmentId?: string) => Promise<void>;
  unarchiveAssignment: (assignmentId?: string) => Promise<void>;
  saveStudentGrade: (
    studentId: string,
    payload: {
      override_score?: number | null;
      comment?: string;
      adopted_coach_excerpts?: Array<{ text: string }>;
      adopt_rubric_suggestion?: boolean;
      rubric_checks?: Array<{ id?: string; pass?: boolean; note?: string }>;
    },
  ) => Promise<void>;
  refreshWorkflowWorkbench: () => void;
  scrollToWorkflowSection: (sectionId: string) => void;
  assignmentWorkflowIndicator: WorkflowIndicator;
  assignmentWorkflowAutoState: string;
  updateDraftRequirement: (key: string, value: unknown) => void;
  updateDraftQuestion: (index: number, patch: UnknownRecord) => void;
}

// ---------------------------------------------------------------------------
// Hook implementation
// ---------------------------------------------------------------------------

export function useAssignmentWorkflow(
  params: UseAssignmentWorkflowParams,
): UseAssignmentWorkflowReturn {
  const {
    apiBase,
    assignmentKind,
    contentSource,
    completionRequiresSubmission,
    completionRequiresDiscussion,
    completionAllowPractice,
    setAssignmentKind,
    setContentSource,
    setCompletionRequiresSubmission,
    setCompletionRequiresDiscussion,
    setCompletionAllowPractice,
    uploadMode,
    uploadAssignmentId,
    uploadDate,
    uploadDueAt,
    uploadSubjectId,
    uploadScope,
    uploadClassName,
    uploadStudentIds,
    uploadFiles,
    uploadAnswerFiles,
    uploading,
    uploadError,
    uploadCardCollapsed,
    uploadJobId,
    uploadJobInfo,
    uploadConfirming,
    uploadDraft,
    draftPanelCollapsed,
    draftError,
    draftActionError,
    misconceptionsText,
    misconceptionsDirty,
    progressAssignmentId,
    setUploadError,
    setUploadStatus,
    setUploadJobId,
    setUploadJobInfo,
    setUploadDraft,
    setUploadFiles,
    setUploadAnswerFiles,
    setUploading,
    setUploadCardCollapsed,
    setUploadConfirming,
    setUploadStatusPollNonce,
    setDraftPanelCollapsed,
    setDraftLoading,
    setDraftError,
    setQuestionShowCount,
    setDraftSaving,
    setDraftActionStatus,
    setDraftActionError,
    setMisconceptionsText,
    setMisconceptionsDirty,
    setProgressPanelCollapsed,
    setProgressAssignmentId,
    setProgressLoading,
    setProgressError,
    setProgressData,
  } = params;

  const [pendingPickerChange, setPendingPickerChange] = useState<PendingPickerChange>(null);

  // ---- Workflow indicator (memoised) ----

  const assignmentWorkflowIndicator = useMemo<WorkflowIndicator>(() => {
    return buildAssignmentWorkflowIndicator({
      uploadJobId,
      uploadJobInfoStatus: uploadJobInfo?.status,
      uploading,
      uploadConfirming,
      uploadDraft,
      uploadError,
      draftError,
      draftActionError,
    });
  }, [
    draftActionError,
    draftError,
    uploadConfirming,
    uploadDraft,
    uploadError,
    uploadJobId,
    uploadJobInfo?.status,
    uploading,
  ]);

  // ---- Workflow step reader ----

  const readWorkflowStepState = useCallback(
    (indicator: WorkflowIndicator, stepKey: string): WorkflowStepState => {
      return indicator.steps.find((step) => step.key === stepKey)?.state || 'todo';
    },
    [],
  );

  // ---- Auto-state derived from indicator ----

  const assignmentWorkflowAutoState = useMemo(() => {
    const uploadStep = readWorkflowStepState(assignmentWorkflowIndicator, 'upload');
    const parseStep = readWorkflowStepState(assignmentWorkflowIndicator, 'parse');
    const reviewStep = readWorkflowStepState(assignmentWorkflowIndicator, 'review');
    const confirmStep = readWorkflowStepState(assignmentWorkflowIndicator, 'confirm');
    if (parseStep === 'error') return 'parse-error';
    if (reviewStep === 'error') return 'review-error';
    if (confirmStep === 'error') return 'confirm-error';
    if (confirmStep === 'done') return 'confirmed';
    if (confirmStep === 'active') return 'confirming';
    if (reviewStep === 'active') return 'review';
    if (parseStep === 'active') return 'parsing';
    if (uploadStep === 'active') return 'uploading';
    return 'idle';
  }, [assignmentWorkflowIndicator, readWorkflowStepState]);

  // ---- Auto-collapse effect driven by workflow state ----

  const assignmentAutoStateRef = useRef('');

  useEffect(() => {
    if (uploadMode !== 'assignment') return;
    if (assignmentAutoStateRef.current === assignmentWorkflowAutoState) return;
    assignmentAutoStateRef.current = assignmentWorkflowAutoState;
    switch (assignmentWorkflowAutoState) {
      case 'uploading':
      case 'parsing':
      case 'parse-error':
        setUploadCardCollapsed(false);
        break;
      case 'review':
      case 'confirming':
        setUploadCardCollapsed(true);
        setDraftPanelCollapsed(false);
        break;
      case 'review-error':
      case 'confirm-error':
        setDraftPanelCollapsed(false);
        break;
      case 'confirmed':
        setUploadCardCollapsed(true);
        setDraftPanelCollapsed(true);
        if (
          (progressAssignmentId || uploadAssignmentId || uploadDraft?.assignment_id || '').trim()
        ) {
          setProgressPanelCollapsed(false);
        }
        break;
      default:
        break;
    }
  }, [
    assignmentWorkflowAutoState,
    progressAssignmentId,
    setDraftPanelCollapsed,
    setProgressPanelCollapsed,
    setUploadCardCollapsed,
    uploadAssignmentId,
    uploadDraft?.assignment_id,
    uploadMode,
  ]);

  // ---- Auto-expand upload card on error ----

  useEffect(() => {
    if (uploadError && uploadCardCollapsed) setUploadCardCollapsed(false);
  }, [setUploadCardCollapsed, uploadError, uploadCardCollapsed]);

  // ---- Auto-expand draft panel on error ----

  useEffect(() => {
    if ((draftError || draftActionError) && draftPanelCollapsed) setDraftPanelCollapsed(false);
  }, [draftActionError, draftError, draftPanelCollapsed, setDraftPanelCollapsed]);

  // ---- Load draft when job finishes parsing ----

  useEffect(() => {
    const uploadJobStatus = uploadJobInfo?.status;
    if (!uploadJobId) return;
    if (uploadJobStatus !== 'done' && uploadJobStatus !== 'confirmed') return;
    let active = true;
    const loadDraft = async () => {
      setDraftError('');
      setDraftLoading(true);
      try {
        const res = await fetch(
          `${apiBase}/assignment/upload/draft?job_id=${encodeURIComponent(uploadJobId)}`,
        );
        if (!res.ok) {
          const text = await res.text();
          throw new Error(text || `状态码 ${res.status}`);
        }
        const data = await res.json();
        if (!active) return;
        const draft = data?.draft as UploadDraft;
        if (!draft) throw new Error('draft 数据缺失');
        const kind = isAssignmentKind(draft.assignment_kind)
          ? draft.assignment_kind
          : isAssignmentKind(uploadJobInfo?.assignment_kind)
            ? uploadJobInfo.assignment_kind
            : undefined;
        const nextDraft: UploadDraft = {
          ...draft,
          questions: Array.isArray(draft.questions) ? draft.questions : [],
          assignment_kind: kind,
          content_source: isContentSource(draft.content_source) ? draft.content_source : 'upload',
        };
        setUploadDraft(nextDraft);
        if (kind) {
          setAssignmentKind(kind);
          setCompletionRequiresSubmission(true);
          setCompletionRequiresDiscussion(kind !== 'problem_set');
          setCompletionAllowPractice(kind === 'problem_set');
        }
        setDraftPanelCollapsed(false);
        setQuestionShowCount(20);
      } catch (err: unknown) {
        if (!active) return;
        setDraftError(toErrorMessage(err));
      } finally {
        if (!active) return;
        setDraftLoading(false);
      }
    };
    loadDraft();
    return () => {
      active = false;
    };
  }, [
    apiBase,
    setAssignmentKind,
    setCompletionAllowPractice,
    setCompletionRequiresDiscussion,
    setCompletionRequiresSubmission,
    setDraftError,
    setDraftLoading,
    setDraftPanelCollapsed,
    setQuestionShowCount,
    setUploadDraft,
    uploadJobId,
    uploadJobInfo?.assignment_kind,
    uploadJobInfo?.status,
  ]);

  // ---- Sync misconceptions text from draft ----

  useEffect(() => {
    if (!uploadDraft) return;
    if (misconceptionsDirty) return;
    const list = Array.isArray(uploadDraft.requirements?.misconceptions)
      ? uploadDraft.requirements.misconceptions
      : [];
    setMisconceptionsText(list.join('\n'));
  }, [
    misconceptionsDirty,
    setMisconceptionsText,
    uploadDraft,
    uploadDraft?.draft_version,
    uploadDraft?.job_id,
  ]);

  // ---- updateDraftRequirement ----

  const updateDraftRequirement = useCallback(
    (key: string, value: unknown) => {
      setUploadDraft((prev) => {
        if (!prev) return prev;
        const nextRequirements = {
          ...(prev.requirements || {}),
          [key]: value,
        };
        const nextMissing = computeLocalRequirementsMissing(
          nextRequirements,
          prev.assignment_kind || assignmentKind,
        );
        return {
          ...prev,
          requirements: nextRequirements,
          requirements_missing: nextMissing,
        };
      });
    },
    [assignmentKind, setUploadDraft],
  );

  // ---- updateDraftQuestion ----

  const updateDraftQuestion = useCallback(
    (index: number, patch: UnknownRecord) => {
      setUploadDraft((prev) => {
        if (!prev) return prev;
        const next = [...(prev.questions || [])];
        const cur = next[index] || {};
        next[index] = { ...cur, ...patch };
        return { ...prev, questions: next };
      });
    },
    [setUploadDraft],
  );

  // ---- fetchAssignmentProgress ----

  const fetchAssignmentProgress = useCallback(
    async (assignmentId?: string) => {
      const aid = (assignmentId || progressAssignmentId || '').trim();
      if (!aid) {
        setProgressError('请先填写作业编号');
        return;
      }
      setProgressLoading(true);
      setProgressError('');
      try {
        const res = await fetch(
          `${apiBase}/teacher/assignment/progress?assignment_id=${encodeURIComponent(aid)}&include_students=true`,
        );
        if (!res.ok) {
          const text = await res.text();
          throw new Error(text || `状态码 ${res.status}`);
        }
        const data = (await res.json()) as AssignmentProgress;
        if (!data?.ok) {
          throw new Error('获取作业完成情况失败');
        }
        setProgressData(data);
        setProgressAssignmentId(data.assignment_id || aid);
      } catch (err: unknown) {
        setProgressError(toErrorMessage(err));
      } finally {
        setProgressLoading(false);
      }
    },
    [
      apiBase,
      progressAssignmentId,
      setProgressAssignmentId,
      setProgressData,
      setProgressError,
      setProgressLoading,
    ],
  );

  const mutateAssignmentVisibility = useCallback(
    async (path: 'archive' | 'unarchive', assignmentId?: string) => {
      const aid = (assignmentId || progressAssignmentId || '').trim();
      if (!aid) {
        setProgressError('请先填写作业编号');
        return;
      }
      setProgressLoading(true);
      setProgressError('');
      try {
        const res = await fetch(`${apiBase}/assignment/${encodeURIComponent(aid)}/${path}`, {
          method: 'POST',
        });
        if (!res.ok) {
          const text = await res.text();
          throw new Error(text || `状态码 ${res.status}`);
        }
        await fetchAssignmentProgress(aid);
      } catch (err: unknown) {
        setProgressError(toErrorMessage(err));
        setProgressLoading(false);
      }
    },
    [apiBase, fetchAssignmentProgress, progressAssignmentId, setProgressError, setProgressLoading],
  );

  const archiveAssignment = useCallback(
    (assignmentId?: string) => mutateAssignmentVisibility('archive', assignmentId),
    [mutateAssignmentVisibility],
  );
  const unarchiveAssignment = useCallback(
    (assignmentId?: string) => mutateAssignmentVisibility('unarchive', assignmentId),
    [mutateAssignmentVisibility],
  );

  const saveStudentGrade = useCallback(
    async (
      studentId: string,
      payload: {
        override_score?: number | null;
        comment?: string;
        adopted_coach_excerpts?: Array<{ text: string }>;
        adopt_rubric_suggestion?: boolean;
        rubric_checks?: Array<{ id?: string; pass?: boolean; note?: string }>;
      },
    ) => {
      const loadedId = String(params.progressData?.assignment_id || '').trim();
      const aid = loadedId || (progressAssignmentId || '').trim();
      const sid = (studentId || '').trim();
      if (!aid || !sid) {
        setProgressError('请先填写作业编号');
        return;
      }
      setProgressLoading(true);
      setProgressError('');
      try {
        const res = await fetch(
          `${apiBase}/teacher/assignment/${encodeURIComponent(aid)}/student/${encodeURIComponent(sid)}/grade`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
          },
        );
        if (!res.ok) {
          const text = await res.text();
          throw new Error(text || `状态码 ${res.status}`);
        }
        await fetchAssignmentProgress(aid);
      } catch (err: unknown) {
        setProgressError(toErrorMessage(err));
        setProgressLoading(false);
      }
    },
    [
      apiBase,
      fetchAssignmentProgress,
      params.progressData?.assignment_id,
      progressAssignmentId,
      setProgressError,
      setProgressLoading,
    ],
  );

  // ---- refreshWorkflowWorkbench ----

  const refreshWorkflowWorkbench = useCallback(() => {
    setUploadStatusPollNonce((n) => n + 1);
    const assignmentId = (
      progressAssignmentId ||
      uploadAssignmentId ||
      uploadDraft?.assignment_id ||
      ''
    ).trim();
    if (assignmentId) {
      void fetchAssignmentProgress(assignmentId);
    }
  }, [
    fetchAssignmentProgress,
    progressAssignmentId,
    setUploadStatusPollNonce,
    uploadAssignmentId,
    uploadDraft?.assignment_id,
  ]);

  // ---- scrollToWorkflowSection ----

  const scrollToWorkflowSection = useCallback((sectionId: string) => {
    if (typeof document === 'undefined') return;
    const node = document.getElementById(sectionId);
    if (!node) return;
    node.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, []);

  // ---- saveDraft ----

  const saveDraft = useCallback(
    async (draft: UploadDraft) => {
      setDraftSaving(true);
      setUploadError('');
      setDraftActionError('');
      setDraftActionStatus('正在保存草稿…');
      try {
        const normalizedRequirements = {
          ...(draft.requirements || {}),
          misconceptions: parseLineList(misconceptionsText),
        };
        const jobId = String(draft.job_id || '').trim();
        const assignmentId = String(draft.assignment_id || '').trim();
        const payload: Record<string, unknown> = {
          requirements: normalizedRequirements,
          questions: draft.questions,
        };
        if (jobId) payload.job_id = jobId;
        else payload.assignment_id = assignmentId;
        const res = await fetch(`${apiBase}/assignment/upload/draft/save`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (!res.ok) {
          const text = await res.text();
          throw new Error(text || `状态码 ${res.status}`);
        }
        const data = await res.json();
        if (data?.requirements_missing) {
          setUploadDraft((prev) =>
            prev
              ? {
                  ...prev,
                  requirements_missing: data.requirements_missing,
                  requirements: normalizedRequirements,
                  draft_saved: true,
                }
              : prev,
          );
        }
        const msg = data?.message || '草稿已保存。';
        setDraftActionStatus(msg);
        setUploadStatus((prev) => `${prev ? prev + '\n\n' : ''}${msg}`);
        setMisconceptionsDirty(false);
      } catch (err: unknown) {
        const message = toErrorMessage(err);
        setDraftActionError(message);
        throw err;
      } finally {
        setDraftSaving(false);
      }
    },
    [
      apiBase,
      misconceptionsText,
      setDraftActionError,
      setDraftActionStatus,
      setDraftSaving,
      setMisconceptionsDirty,
      setUploadDraft,
      setUploadError,
      setUploadStatus,
    ],
  );

  // ---- handleUploadAssignment ----

  const handleUploadAssignment = useCallback(
    async (event: FormEvent) => {
      event.preventDefault();
      setUploadError('');
      setUploadStatus('');
      setUploadJobId('');
      setUploadJobInfo(null);
      setUploadDraft(null);
      setDraftPanelCollapsed(false);
      setDraftError('');
      setDraftActionStatus('');
      setDraftActionError('');
      setUploadCardCollapsed(false);
      if (!uploadAssignmentId.trim()) {
        setUploadError('请填写作业编号');
        return;
      }
      if (!uploadFiles.length) {
        setUploadError('请至少上传一份作业文件（文档或图片）');
        return;
      }
      const sourceFileCheck = validateFilesBeforeUpload(uploadFiles, {
        label: '作业文件',
        maxCount: ASSIGNMENT_UPLOAD_MAX_FILES_PER_FIELD,
        maxFileBytes: ASSIGNMENT_UPLOAD_MAX_FILE_BYTES,
        allowedSuffixes: ASSIGNMENT_UPLOAD_ALLOWED_SUFFIXES,
      });
      if (sourceFileCheck) {
        setUploadError(sourceFileCheck);
        return;
      }
      const answerFileCheck = validateFilesBeforeUpload(uploadAnswerFiles, {
        label: '答案文件',
        maxCount: ASSIGNMENT_UPLOAD_MAX_FILES_PER_FIELD,
        maxFileBytes: ASSIGNMENT_UPLOAD_MAX_FILE_BYTES,
        allowedSuffixes: ASSIGNMENT_UPLOAD_ALLOWED_SUFFIXES,
      });
      if (answerFileCheck) {
        setUploadError(answerFileCheck);
        return;
      }
      const totalUploadBytes = [...uploadFiles, ...uploadAnswerFiles].reduce(
        (sum, file) => sum + Math.max(0, Number(file.size || 0)),
        0,
      );
      if (totalUploadBytes > ASSIGNMENT_UPLOAD_MAX_TOTAL_BYTES) {
        setUploadError(
          `作业上传总大小不能超过 ${ASSIGNMENT_UPLOAD_MAX_TOTAL_BYTES / (1024 * 1024)}MB`,
        );
        return;
      }
      if (uploadScope === 'student' && !uploadStudentIds.trim()) {
        setUploadError('私人作业请填写学生编号');
        return;
      }
      if (uploadScope === 'class' && !uploadClassName.trim()) {
        setUploadError('班级作业请填写班级');
        return;
      }
      if (!uploadSubjectId.trim()) {
        setUploadError('请选择学科');
        return;
      }
      setUploading(true);
      try {
        const fd = new FormData();
        fd.append('assignment_id', uploadAssignmentId.trim());
        if (uploadDate.trim()) fd.append('date', uploadDate.trim());
        if (uploadDueAt.trim()) fd.append('due_at', uploadDueAt.trim());
        fd.append('subject_id', uploadSubjectId.trim());
        fd.append('scope', uploadScope);
        if (uploadClassName.trim()) fd.append('class_name', uploadClassName.trim());
        if (uploadStudentIds.trim()) fd.append('student_ids', uploadStudentIds.trim());
        fd.append('assignment_kind', assignmentKind);
        uploadFiles.forEach((file) => fd.append('files', file));
        uploadAnswerFiles.forEach((file) => fd.append('answer_files', file));

        const res = await fetch(`${apiBase}/assignment/upload/start`, { method: 'POST', body: fd });
        if (!res.ok) {
          const text = await res.text();
          let message = text || `状态码 ${res.status}`;
          try {
            const parsed = JSON.parse(text);
            const detail = parsed?.detail || parsed;
            if (typeof detail === 'string') {
              message = detail;
            } else if (detail?.message) {
              const hints = Array.isArray(detail.hints) ? detail.hints.join('；') : '';
              message = `${detail.message}${hints ? `（${hints}）` : ''}`;
            }
          } catch (err) {
            // ignore JSON parse errors
          }
          throw new Error(message);
        }
        const data = await res.json();
        if (data && typeof data === 'object') {
          if (data.job_id) {
            const jid = String(data.job_id);
            setUploadJobId(jid);
            try {
              safeLocalStorageSetItem(
                'teacherActiveUpload',
                JSON.stringify({
                  type: 'assignment',
                  job_id: jid,
                  assignment_kind: assignmentKind,
                }),
              );
            } catch {
              // ignore
            }
          }
          const message = data.message || '解析任务已创建，后台处理中。';
          setUploadStatus(message);
        } else {
          setUploadStatus(typeof data === 'string' ? data : JSON.stringify(data, null, 2));
        }
        setUploadFiles([]);
        setUploadAnswerFiles([]);
      } catch (err: unknown) {
        setUploadError(toErrorMessage(err));
      } finally {
        setUploading(false);
      }
    },
    [
      apiBase,
      setDraftActionError,
      setDraftActionStatus,
      setDraftError,
      setDraftPanelCollapsed,
      setUploadAnswerFiles,
      setUploadCardCollapsed,
      setUploadDraft,
      setUploadError,
      setUploadFiles,
      setUploadJobId,
      setUploadJobInfo,
      setUploadStatus,
      setUploading,
      assignmentKind,
      uploadAnswerFiles,
      uploadAssignmentId,
      uploadClassName,
      uploadDate,
      uploadDueAt,
      uploadSubjectId,
      uploadFiles,
      uploadScope,
      uploadStudentIds,
    ],
  );

  // ---- handleConfirmUpload ----

  const handleConfirmUpload = useCallback(async () => {
    const assignmentId = String(uploadDraft?.assignment_id || '').trim();
    const draftJobId = String(uploadDraft?.job_id || '').trim();
    const folderDraft = Boolean(assignmentId && !draftJobId);
    const resolvedJobId = folderDraft
      ? ''
      : (() => {
          const jobId = String(uploadJobId || draftJobId || '').trim();
          if (jobId) return jobId;
          try {
            const raw = safeLocalStorageGetItem('teacherActiveUpload');
            if (!raw) return '';
            const active = JSON.parse(raw);
            if (active?.type === 'assignment' && active?.job_id)
              return String(active.job_id).trim();
          } catch {
            // ignore
          }
          return '';
        })();
    if (!resolvedJobId && !assignmentId) {
      const message = '请先生成或上传作业草稿';
      setUploadError(message);
      setDraftActionError(message);
      return;
    }
    if (resolvedJobId && !uploadJobId) setUploadJobId(resolvedJobId);
    const previousUploadJobInfo = uploadJobInfo ? { ...uploadJobInfo } : null;
    const draftKind =
      uploadDraft && isAssignmentKind(uploadDraft.assignment_kind)
        ? uploadDraft.assignment_kind
        : assignmentKind;
    const completionPolicyOverride = {
      requires_submission: completionRequiresSubmission,
      requires_discussion: completionRequiresDiscussion,
      allow_practice: draftKind === 'problem_set' ? completionAllowPractice : false,
    };
    setUploadError('');
    setDraftActionError('');
    setDraftActionStatus('正在发布草稿…');
    setUploadConfirming(true);
    try {
      // If parsing is still running, don't attempt to confirm.
      if (
        resolvedJobId &&
        uploadJobInfo &&
        uploadJobInfo.status !== 'done' &&
        uploadJobInfo.status !== 'confirmed' &&
        uploadJobInfo.status !== 'created'
      ) {
        const message = '解析尚未完成，请等待解析完成后再发布草稿。';
        setUploadError(message);
        setDraftActionError(message);
        setUploadStatusPollNonce((n) => n + 1);
        return;
      }
      if (resolvedJobId) {
        setUploadJobInfo((prev) =>
          prev
            ? {
                ...prev,
                status:
                  prev.status === 'confirmed' || prev.status === 'created'
                    ? 'confirmed'
                    : 'confirming',
                step: 'confirming',
                progress: prev.progress ?? 0,
              }
            : {
                job_id: resolvedJobId,
                status: 'confirming',
                step: 'confirming',
                progress: 0,
              },
        );
      }
      if (uploadDraft) {
        await saveDraft(uploadDraft);
      }
      const res = await fetch(`${apiBase}/assignment/upload/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(
          resolvedJobId
            ? {
                job_id: resolvedJobId,
                strict_requirements: true,
                completion_policy_override: completionPolicyOverride,
              }
            : {
                assignment_id: assignmentId,
                strict_requirements: true,
                completion_policy_override: completionPolicyOverride,
              },
        ),
      });
      if (!res.ok) {
        const text = await res.text();
        let message = text || `状态码 ${res.status}`;
        try {
          const parsed = JSON.parse(text);
          const detail = parsed?.detail || parsed;
          if (typeof detail === 'string') message = detail;
          if (detail?.message) message = detail.message;
          if (detail?.error === 'job_not_ready') {
            const progress = detail?.progress !== undefined ? `（进度 ${detail.progress}%）` : '';
            message = `${detail.message || '解析尚未完成'}${progress}`;
            setUploadStatusPollNonce((n) => n + 1);
          }
          if (detail?.missing && Array.isArray(detail.missing)) {
            message = `${detail.message || '作业要求未补全'}：${formatMissingRequirements(detail.missing)}`;
          }
        } catch {
          // ignore
        }
        throw new Error(message);
      }
      const data = await res.json();
      if (data && typeof data === 'object') {
        const lines: string[] = [];
        lines.push(data.message || '作业已发布草稿。');
        if (data.assignment_id) lines.push(`作业编号：${data.assignment_id}`);
        if (data.question_count !== undefined) lines.push(`题目数量：${data.question_count}`);
        if (Array.isArray(data.requirements_missing) && data.requirements_missing.length) {
          lines.push(`作业要求缺失项：${formatMissingRequirements(data.requirements_missing)}`);
        }
        if (Array.isArray(data.warnings) && data.warnings.length) {
          lines.push(`解析提示：${data.warnings.join('；')}`);
        }
        const msg = lines.join('\n');
        setDraftActionStatus(msg);
        setUploadStatus(msg);
        setUploadJobInfo((prev) =>
          prev
            ? { ...prev, status: 'confirmed' }
            : resolvedJobId
              ? { job_id: resolvedJobId, status: 'confirmed' }
              : { job_id: assignmentId, assignment_id: assignmentId, status: 'confirmed' },
        );
        setDraftPanelCollapsed(true);
        try {
          const raw = safeLocalStorageGetItem('teacherActiveUpload');
          if (raw) {
            const active = JSON.parse(raw);
            if (active?.type === 'assignment' && active?.job_id === resolvedJobId)
              safeLocalStorageRemoveItem('teacherActiveUpload');
          }
        } catch {
          // ignore
        }
        if (data.assignment_id) {
          setProgressAssignmentId(data.assignment_id);
          setProgressPanelCollapsed(false);
          void fetchAssignmentProgress(data.assignment_id);
        }
      }
    } catch (err: unknown) {
      const message = toErrorMessage(err);
      setUploadError(message);
      setDraftActionError(message);
      setUploadJobInfo((prev) => {
        if (!prev || prev.status !== 'confirming') return prev;
        if (previousUploadJobInfo) {
          return {
            ...prev,
            status: previousUploadJobInfo.status,
            step: previousUploadJobInfo.step ?? prev.step,
            progress: previousUploadJobInfo.progress ?? prev.progress,
          };
        }
        return { ...prev, status: 'done', step: 'parsed', progress: prev.progress ?? 100 };
      });
      setUploadStatusPollNonce((n) => n + 1);
    } finally {
      setUploadConfirming(false);
    }
  }, [
    apiBase,
    assignmentKind,
    completionAllowPractice,
    completionRequiresDiscussion,
    completionRequiresSubmission,
    fetchAssignmentProgress,
    saveDraft,
    setDraftActionError,
    setDraftActionStatus,
    setDraftPanelCollapsed,
    setProgressAssignmentId,
    setProgressPanelCollapsed,
    setUploadConfirming,
    setUploadError,
    setUploadJobId,
    setUploadJobInfo,
    setUploadStatus,
    setUploadStatusPollNonce,
    uploadDraft,
    uploadJobId,
    uploadJobInfo,
  ]);

  const clearActiveDraft = useCallback(() => {
    setUploadDraft(null);
    setUploadJobId('');
    setUploadJobInfo(null);
    setDraftError('');
    setDraftActionError('');
    setDraftActionStatus('');
    setMisconceptionsText('');
    setMisconceptionsDirty(false);
    try {
      safeLocalStorageRemoveItem('teacherActiveUpload');
    } catch {
      // ignore
    }
  }, [
    setDraftActionError,
    setDraftActionStatus,
    setDraftError,
    setMisconceptionsDirty,
    setMisconceptionsText,
    setUploadDraft,
    setUploadJobId,
    setUploadJobInfo,
  ]);

  const applyAssignmentKind = useCallback(
    (next: AssignmentKind) => {
      setAssignmentKind(next);
      if (next !== 'problem_set' && contentSource === 'bank') {
        setContentSource('upload');
      }
      setCompletionRequiresSubmission(true);
      setCompletionRequiresDiscussion(next !== 'problem_set');
      setCompletionAllowPractice(next === 'problem_set');
    },
    [
      contentSource,
      setAssignmentKind,
      setCompletionAllowPractice,
      setCompletionRequiresDiscussion,
      setCompletionRequiresSubmission,
      setContentSource,
    ],
  );

  const requestAssignmentKindChange = useCallback(
    (next: AssignmentKind) => {
      if (next === assignmentKind) return;
      if (uploadDraft) {
        setPendingPickerChange({ type: 'kind', value: next });
        return;
      }
      applyAssignmentKind(next);
    },
    [applyAssignmentKind, assignmentKind, uploadDraft],
  );

  const requestContentSourceChange = useCallback(
    (next: ContentSource) => {
      if (next === contentSource) return;
      if (next === 'bank' && assignmentKind !== 'problem_set') return;
      if (uploadDraft) {
        setPendingPickerChange({ type: 'source', value: next });
        return;
      }
      setContentSource(next);
    },
    [assignmentKind, contentSource, setContentSource, uploadDraft],
  );

  const confirmPendingPickerChange = useCallback(() => {
    const pending = pendingPickerChange;
    setPendingPickerChange(null);
    if (!pending) return;
    clearActiveDraft();
    if (pending.type === 'kind') {
      applyAssignmentKind(pending.value as AssignmentKind);
      return;
    }
    setContentSource(pending.value as ContentSource);
  }, [applyAssignmentKind, clearActiveDraft, pendingPickerChange, setContentSource]);

  const cancelPendingPickerChange = useCallback(() => {
    setPendingPickerChange(null);
  }, []);

  const applyFolderDraft = useCallback(
    (raw: Partial<UploadDraft> | null | undefined, source: ContentSource) => {
      const draft = toFolderDraft(raw, {
        date: uploadDate,
        dueAt: uploadDueAt,
        scope: uploadScope as UploadDraft['scope'],
        className: uploadClassName,
        studentIds: uploadStudentIds,
        assignmentKind,
        contentSource: source,
      });
      setUploadJobId('');
      setUploadJobInfo(null);
      try {
        safeLocalStorageRemoveItem('teacherActiveUpload');
      } catch {
        // ignore
      }
      setUploadDraft(draft);
      if (isAssignmentKind(draft.assignment_kind)) {
        setAssignmentKind(draft.assignment_kind);
        setCompletionRequiresSubmission(true);
        setCompletionRequiresDiscussion(draft.assignment_kind !== 'problem_set');
        setCompletionAllowPractice(draft.assignment_kind === 'problem_set');
      }
      if (isContentSource(draft.content_source)) {
        setContentSource(
          draft.assignment_kind &&
            draft.assignment_kind !== 'problem_set' &&
            draft.content_source === 'bank'
            ? 'upload'
            : draft.content_source,
        );
      }
      setDraftPanelCollapsed(false);
      setQuestionShowCount(20);
      setMisconceptionsDirty(false);
    },
    [
      assignmentKind,
      setAssignmentKind,
      setCompletionAllowPractice,
      setCompletionRequiresDiscussion,
      setCompletionRequiresSubmission,
      setContentSource,
      setDraftPanelCollapsed,
      setMisconceptionsDirty,
      setQuestionShowCount,
      setUploadDraft,
      setUploadJobId,
      setUploadJobInfo,
      uploadClassName,
      uploadDate,
      uploadDueAt,
      uploadScope,
      uploadStudentIds,
    ],
  );

  const handleFromBank = useCallback(
    async (input: { kp: string; count: number }) => {
      if (assignmentKind !== 'problem_set') return;
      const assignmentId = uploadAssignmentId.trim();
      if (!assignmentId) {
        setUploadError('请填写作业编号');
        return;
      }
      if (!uploadSubjectId.trim()) {
        setUploadError('请选择学科');
        return;
      }
      setUploading(true);
      setUploadError('');
      setUploadStatus('');
      setDraftActionError('');
      setDraftActionStatus('正在从题库选题…');
      try {
        const fd = new FormData();
        fd.append('assignment_id', assignmentId);
        fd.append('subject_id', uploadSubjectId.trim());
        fd.append('kp', input.kp);
        fd.append('count', String(clampQuestionCount(input.count)));
        if (uploadDate.trim()) fd.append('date', uploadDate.trim());
        if (uploadDueAt.trim()) fd.append('due_at', uploadDueAt.trim());
        if (uploadClassName.trim()) fd.append('class_name', uploadClassName.trim());
        if (uploadStudentIds.trim()) fd.append('student_ids', uploadStudentIds.trim());
        const res = await fetch(`${apiBase}/assignment/draft/from-bank`, {
          method: 'POST',
          body: fd,
        });
        if (!res.ok) {
          const text = await res.text();
          throw new Error(text || `状态码 ${res.status}`);
        }
        const data = await res.json();
        applyFolderDraft(data?.draft, 'bank');
        const msg = data?.message || '已从题库生成草稿，请审核后发布。';
        setDraftActionStatus(msg);
        setUploadStatus(msg);
      } catch (err: unknown) {
        const message = toErrorMessage(err);
        setUploadError(message);
        setDraftActionError(message);
      } finally {
        setUploading(false);
      }
    },
    [
      apiBase,
      applyFolderDraft,
      assignmentKind,
      setDraftActionError,
      setDraftActionStatus,
      setUploadError,
      setUploadStatus,
      setUploading,
      uploadAssignmentId,
      uploadClassName,
      uploadDate,
      uploadDueAt,
      uploadStudentIds,
      uploadSubjectId,
    ],
  );

  const handleGenerate = useCallback(
    async (input: {
      kp: string;
      perKp: number;
      topic: string;
      gradeLevel: string;
      seed: string;
    }) => {
      const assignmentId = uploadAssignmentId.trim();
      if (!assignmentId) {
        setUploadError('请填写作业编号');
        return;
      }
      if (!uploadSubjectId.trim()) {
        setUploadError('请选择学科');
        return;
      }
      if (assignmentKind !== 'problem_set' && (!input.topic.trim() || !input.gradeLevel.trim())) {
        setUploadError('请填写主题和年级');
        return;
      }
      setUploading(true);
      setUploadError('');
      setUploadStatus('');
      setDraftActionError('');
      setDraftActionStatus('正在生成草稿…');
      try {
        const fd = new FormData();
        fd.append('assignment_id', assignmentId);
        fd.append('assignment_kind', assignmentKind);
        fd.append('content_source', 'ai');
        fd.append('generate', 'true');
        fd.append('subject_id', uploadSubjectId.trim());
        if (uploadDate.trim()) fd.append('date', uploadDate.trim());
        if (uploadDueAt.trim()) fd.append('due_at', uploadDueAt.trim());
        if (uploadClassName.trim()) fd.append('class_name', uploadClassName.trim());
        if (uploadStudentIds.trim()) fd.append('student_ids', uploadStudentIds.trim());
        if (assignmentKind === 'problem_set') {
          fd.append('kp', input.kp);
          fd.append('per_kp', String(clampQuestionCount(input.perKp)));
        } else {
          fd.append(
            'requirements_json',
            JSON.stringify({
              subject: uploadSubjectId.trim(),
              topic: input.topic.trim(),
              grade_level: input.gradeLevel.trim(),
            }),
          );
          if (input.seed.trim()) fd.append('seed', input.seed.trim());
        }
        const res = await fetch(`${apiBase}/assignment/generate`, { method: 'POST', body: fd });
        if (!res.ok) {
          const text = await res.text();
          throw new Error(text || `状态码 ${res.status}`);
        }
        const data = await res.json();
        applyFolderDraft(data?.draft, 'ai');
        const msg = data?.message || 'AI 草稿已生成，请审核后发布。';
        setDraftActionStatus(msg);
        setUploadStatus(msg);
      } catch (err: unknown) {
        const message = toErrorMessage(err);
        setUploadError(message);
        setDraftActionError(message);
      } finally {
        setUploading(false);
      }
    },
    [
      apiBase,
      applyFolderDraft,
      assignmentKind,
      setDraftActionError,
      setDraftActionStatus,
      setUploadError,
      setUploadStatus,
      setUploading,
      uploadAssignmentId,
      uploadClassName,
      uploadDate,
      uploadDueAt,
      uploadStudentIds,
      uploadSubjectId,
    ],
  );

  return {
    handleUploadAssignment,
    handleFromBank,
    handleGenerate,
    requestAssignmentKindChange,
    requestContentSourceChange,
    pendingPickerChange,
    confirmPendingPickerChange,
    cancelPendingPickerChange,
    saveDraft,
    handleConfirmUpload,
    fetchAssignmentProgress,
    archiveAssignment,
    unarchiveAssignment,
    saveStudentGrade,
    refreshWorkflowWorkbench,
    scrollToWorkflowSection,
    assignmentWorkflowIndicator,
    assignmentWorkflowAutoState,
    updateDraftRequirement,
    updateDraftQuestion,
  };
}
