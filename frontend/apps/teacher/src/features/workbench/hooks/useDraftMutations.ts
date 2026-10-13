import { useCallback } from 'react';
import { computeLocalRequirementsMissing, parseLineList } from '../workbenchUtils';
import { toUserFacingErrorMessage } from '../../../../../shared/errorMessage';
import type { UploadDraft } from '../../../appTypes';
import type { UseAssignmentWorkflowParams } from '../../../types/workflow';

const toErrorMessage = (error: unknown, fallback = '请求失败') => {
  return toUserFacingErrorMessage(error, fallback);
};

export function useDraftMutations(params: UseAssignmentWorkflowParams) {
  const {
    apiBase,
    assignmentKind,
    misconceptionsText,
    setUploadDraft,
    setUploadError,
    setUploadStatus,
    setDraftSaving,
    setDraftActionStatus,
    setDraftActionError,
    setMisconceptionsDirty,
  } = params;

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

  const updateDraftQuestion = useCallback(
    (index: number, patch: Record<string, unknown>) => {
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

  return {
    updateDraftRequirement,
    updateDraftQuestion,
    saveDraft,
  };
}
