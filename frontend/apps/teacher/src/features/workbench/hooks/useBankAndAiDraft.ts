import { useCallback, useState } from 'react';
import {
  clampQuestionCount,
  isAssignmentKind,
  isContentSource,
  parseCommaList,
} from '../workbenchUtils';
import { safeLocalStorageRemoveItem } from '../../../utils/storage';
import { toUserFacingErrorMessage } from '../../../../../shared/errorMessage';
import type { AssignmentKind, ContentSource, UploadDraft } from '../../../appTypes';
import type { PendingPickerChange, UseAssignmentWorkflowParams } from '../../../types/workflow';

const toErrorMessage = (error: unknown, fallback = '请求失败') => {
  return toUserFacingErrorMessage(error, fallback);
};

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

export function useBankAndAiDraft(params: UseAssignmentWorkflowParams) {
  const {
    apiBase,
    assignmentKind,
    contentSource,
    uploadAssignmentId,
    uploadDate,
    uploadDueAt,
    uploadSubjectId,
    uploadScope,
    uploadClassName,
    uploadStudentIds,
    uploadDraft,
    setAssignmentKind,
    setContentSource,
    setCompletionRequiresSubmission,
    setCompletionRequiresDiscussion,
    setCompletionAllowPractice,
    setUploadError,
    setUploadStatus,
    setUploadJobId,
    setUploadJobInfo,
    setUploadDraft,
    setUploading,
    setDraftPanelCollapsed,
    setDraftError,
    setQuestionShowCount,
    setDraftActionStatus,
    setDraftActionError,
    setMisconceptionsText,
    setMisconceptionsDirty,
  } = params;

  const [pendingPickerChange, setPendingPickerChange] = useState<PendingPickerChange>(null);

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
    handleFromBank,
    handleGenerate,
    requestAssignmentKindChange,
    requestContentSourceChange,
    pendingPickerChange,
    confirmPendingPickerChange,
    cancelPendingPickerChange,
  };
}
