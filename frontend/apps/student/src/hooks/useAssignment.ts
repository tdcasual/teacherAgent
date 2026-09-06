import { useEffect, type Dispatch } from 'react';
import type { TodayAssignmentItem } from '../appTypes';
import {
  isAbortError,
  toErrorMessage,
  todayDate,
  type StudentAction,
  type StudentState,
} from './useStudentState';

type UseAssignmentParams = {
  state: StudentState;
  dispatch: Dispatch<StudentAction>;
};

const toTodayItems = (payload: unknown): TodayAssignmentItem[] => {
  if (!payload || typeof payload !== 'object') return [];
  const raw = (payload as { assignments?: unknown }).assignments;
  if (!Array.isArray(raw)) return [];
  const items: TodayAssignmentItem[] = [];
  for (const entry of raw) {
    if (!entry || typeof entry !== 'object') continue;
    const item = entry as Record<string, unknown>;
    const assignmentId = String(item.assignment_id || '').trim();
    if (!assignmentId) continue;
    const progressRaw =
      item.progress && typeof item.progress === 'object'
        ? (item.progress as Record<string, unknown>)
        : {};
    const score = progressRaw.official_score;
    items.push({
      assignment_id: assignmentId,
      teacher_id: String(item.teacher_id || '').trim(),
      subject_id: String(item.subject_id || '').trim(),
      title: String(item.title || assignmentId).trim() || assignmentId,
      due_at: item.due_at ? String(item.due_at) : '',
      progress: {
        submitted: Boolean(progressRaw.submitted),
        overdue: Boolean(progressRaw.overdue),
        official_score: typeof score === 'number' ? score : null,
        process_archive_status: String(progressRaw.process_archive_status || 'none'),
      },
    });
  }
  return items;
};

export function useAssignment({ state, dispatch }: UseAssignmentParams) {
  const { apiBase, verifiedStudent, assignmentRefreshNonce } = state;

  useEffect(() => {
    const sid = verifiedStudent?.student_id?.trim() || '';
    if (!sid) {
      dispatch({
        type: 'BATCH',
        actions: [
          { type: 'SET', field: 'todayAssignment', value: null },
          { type: 'SET', field: 'todayAssignments', value: [] },
          { type: 'SET', field: 'assignmentError', value: '' },
          { type: 'SET', field: 'assignmentLoading', value: false },
        ],
      });
      return;
    }
    const controller = new AbortController();
    dispatch({
      type: 'BATCH',
      actions: [
        { type: 'SET', field: 'assignmentLoading', value: true },
        { type: 'SET', field: 'assignmentError', value: '' },
      ],
    });
    const timer = setTimeout(async () => {
      try {
        const date = todayDate();
        const url = new URL(`${apiBase}/assignment/today`);
        url.searchParams.set('student_id', sid);
        url.searchParams.set('date', date);
        const res = await fetch(url.toString(), { signal: controller.signal });
        if (!res.ok) {
          const text = await res.text();
          throw new Error(text || `状态码 ${res.status}`);
        }
        const data = await res.json();
        const assignments = toTodayItems(data);
        const first = assignments[0];
        dispatch({
          type: 'BATCH',
          actions: [
            { type: 'SET', field: 'todayAssignments', value: assignments },
            {
              type: 'SET',
              field: 'todayAssignment',
              value: first ? { assignment_id: first.assignment_id, date } : null,
            },
          ],
        });
      } catch (err: unknown) {
        if (isAbortError(err)) return;
        dispatch({
          type: 'BATCH',
          actions: [
            {
              type: 'SET',
              field: 'assignmentError',
              value: toErrorMessage(err, '无法获取今日作业'),
            },
            { type: 'SET', field: 'todayAssignment', value: null },
            { type: 'SET', field: 'todayAssignments', value: [] },
          ],
        });
      } finally {
        dispatch({ type: 'SET', field: 'assignmentLoading', value: false });
      }
    }, 300);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [verifiedStudent, apiBase, assignmentRefreshNonce, dispatch]);
}
