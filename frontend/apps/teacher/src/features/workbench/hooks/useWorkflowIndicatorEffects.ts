import { useCallback, useEffect, useMemo, useRef } from 'react';
import { buildAssignmentWorkflowIndicator } from '../workflowIndicators';
import { isAssignmentKind, isContentSource } from '../workbenchUtils';
import { toUserFacingErrorMessage } from '../../../../../shared/errorMessage';
import type { UploadDraft, WorkflowIndicator, WorkflowStepState } from '../../../appTypes';
import type { UseAssignmentWorkflowParams } from '../../../types/workflow';

const toErrorMessage = (error: unknown, fallback = '请求失败') => {
  return toUserFacingErrorMessage(error, fallback);
};

export function useWorkflowIndicatorEffects(params: UseAssignmentWorkflowParams) {
  const {
    apiBase,
    uploadMode,
    uploadAssignmentId,
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
    misconceptionsDirty,
    progressAssignmentId,
    setAssignmentKind,
    setCompletionRequiresSubmission,
    setCompletionRequiresDiscussion,
    setCompletionAllowPractice,
    setUploadCardCollapsed,
    setUploadDraft,
    setDraftPanelCollapsed,
    setDraftLoading,
    setDraftError,
    setQuestionShowCount,
    setMisconceptionsText,
    setProgressPanelCollapsed,
  } = params;

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

  const readWorkflowStepState = useCallback(
    (indicator: WorkflowIndicator, stepKey: string): WorkflowStepState => {
      return indicator.steps.find((step) => step.key === stepKey)?.state || 'todo';
    },
    [],
  );

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

  useEffect(() => {
    if (uploadError && uploadCardCollapsed) setUploadCardCollapsed(false);
  }, [setUploadCardCollapsed, uploadError, uploadCardCollapsed]);

  useEffect(() => {
    if ((draftError || draftActionError) && draftPanelCollapsed) setDraftPanelCollapsed(false);
  }, [draftActionError, draftError, draftPanelCollapsed, setDraftPanelCollapsed]);

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

  return {
    assignmentWorkflowIndicator,
    assignmentWorkflowAutoState,
  };
}
