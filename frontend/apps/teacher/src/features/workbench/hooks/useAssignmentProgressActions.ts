import { useCallback } from 'react';
import { toUserFacingErrorMessage } from '../../../../../shared/errorMessage';
import type { AssignmentProgress } from '../../../appTypes';
import type { UseAssignmentWorkflowParams } from '../../../types/workflow';

const toErrorMessage = (error: unknown, fallback = '请求失败') => {
  return toUserFacingErrorMessage(error, fallback);
};

export function useAssignmentProgressActions(params: UseAssignmentWorkflowParams) {
  const {
    apiBase,
    uploadAssignmentId,
    uploadDraft,
    progressAssignmentId,
    progressData,
    setUploadStatusPollNonce,
    setProgressAssignmentId,
    setProgressLoading,
    setProgressError,
    setProgressData,
  } = params;

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
      const loadedId = String(progressData?.assignment_id || '').trim();
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
      progressData?.assignment_id,
      progressAssignmentId,
      setProgressError,
      setProgressLoading,
    ],
  );

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

  const scrollToWorkflowSection = useCallback((sectionId: string) => {
    if (typeof document === 'undefined') return;
    const node = document.getElementById(sectionId);
    if (!node) return;
    node.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, []);

  return {
    fetchAssignmentProgress,
    archiveAssignment,
    unarchiveAssignment,
    saveStudentGrade,
    refreshWorkflowWorkbench,
    scrollToWorkflowSection,
  };
}
