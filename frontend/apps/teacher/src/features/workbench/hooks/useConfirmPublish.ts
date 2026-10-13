import { useCallback } from 'react';
import { formatMissingRequirements, isAssignmentKind } from '../workbenchUtils';
import { safeLocalStorageGetItem, safeLocalStorageRemoveItem } from '../../../utils/storage';
import { toUserFacingErrorMessage } from '../../../../../shared/errorMessage';
import type { AssignmentKind, UploadDraft, UploadJobStatus } from '../../../appTypes';

const toErrorMessage = (error: unknown, fallback = '请求失败') => {
  return toUserFacingErrorMessage(error, fallback);
};

export type UseConfirmPublishParams = {
  apiBase: string;
  assignmentKind: AssignmentKind;
  completionRequiresSubmission: boolean;
  completionRequiresDiscussion: boolean;
  completionAllowPractice: boolean;
  uploadJobId: string;
  uploadJobInfo: UploadJobStatus | null;
  uploadDraft: UploadDraft | null;
  saveDraft: (draft: UploadDraft) => Promise<void>;
  fetchAssignmentProgress: (assignmentId?: string) => Promise<void>;
  setUploadError: (value: string) => void;
  setUploadStatus: (value: string | ((prev: string) => string)) => void;
  setUploadJobId: (value: string) => void;
  setUploadJobInfo: (
    value: UploadJobStatus | null | ((prev: UploadJobStatus | null) => UploadJobStatus | null),
  ) => void;
  setUploadConfirming: (value: boolean) => void;
  setUploadStatusPollNonce: (value: number | ((prev: number) => number)) => void;
  setDraftPanelCollapsed: (value: boolean | ((prev: boolean) => boolean)) => void;
  setDraftActionStatus: (value: string) => void;
  setDraftActionError: (value: string) => void;
  setProgressPanelCollapsed: (value: boolean | ((prev: boolean) => boolean)) => void;
  setProgressAssignmentId: (value: string) => void;
};

export function useConfirmPublish(params: UseConfirmPublishParams) {
  const {
    apiBase,
    assignmentKind,
    completionRequiresSubmission,
    completionRequiresDiscussion,
    completionAllowPractice,
    uploadJobId,
    uploadJobInfo,
    uploadDraft,
    saveDraft,
    fetchAssignmentProgress,
    setUploadError,
    setUploadStatus,
    setUploadJobId,
    setUploadJobInfo,
    setUploadConfirming,
    setUploadStatusPollNonce,
    setDraftPanelCollapsed,
    setDraftActionStatus,
    setDraftActionError,
    setProgressPanelCollapsed,
    setProgressAssignmentId,
  } = params;

  const handleConfirmUpload = useCallback(async () => {
    const assignmentId = String(uploadDraft?.assignment_id || '').trim();
    const draftJobId = String(uploadDraft?.job_id || '').trim();
    const folderDraft = Boolean(assignmentId && !draftJobId);
    // leftover teacherActiveUpload must not beat a folder draft locator
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

  return { handleConfirmUpload };
}
