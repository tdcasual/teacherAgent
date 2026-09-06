export type StudentSubmitResult = {
  ok: boolean;
  submitted: boolean;
  assignment_id: string;
  attempt_id: string;
  official_score: number | null;
  reason: string;
  message: string;
};

const NOT_COUNTED_MESSAGE = '未记为提交。有效评分不足，请补充作业材料后再交。';
const PROGRESS_UNAVAILABLE_MESSAGE = '未记为提交。暂时无法确认评分结果，请稍后在作业记录中查看。';

export function matchReadyChatFiles(ready: Array<{ fileName: string }>, files: File[]): File[] {
  const remaining = [...files];
  const matched: File[] = [];
  for (const item of ready) {
    const name = String(item.fileName || '').trim();
    if (!name) return [];
    const index = remaining.findIndex((file) => file.name === name);
    if (index < 0) return [];
    matched.push(remaining[index]);
    remaining.splice(index, 1);
  }
  return matched;
}

const asRecord = (value: unknown): Record<string, unknown> =>
  value && typeof value === 'object' ? (value as Record<string, unknown>) : {};

export function parseStudentSubmitResponse(
  payload: unknown,
  httpStatus: number,
): StudentSubmitResult {
  const record = asRecord(payload);
  const assignmentId = String(record.assignment_id || '').trim();
  const attemptId = String(record.attempt_id || '').trim();
  const reason = String(record.reason || '').trim();
  const okHttp = httpStatus >= 200 && httpStatus < 300;
  const okBody = record.ok !== false;
  const submitted = Boolean(record.submitted);
  const score = typeof record.official_score === 'number' ? record.official_score : null;
  if (!okHttp || !okBody) {
    return {
      ok: false,
      submitted: false,
      assignment_id: assignmentId,
      attempt_id: attemptId,
      official_score: null,
      reason: reason || 'submit_failed',
      message: '提交失败，请稍后重试。',
    };
  }
  if (!submitted) {
    const resolvedReason = reason || 'min_graded_total';
    return {
      ok: true,
      submitted: false,
      assignment_id: assignmentId,
      attempt_id: attemptId,
      official_score: null,
      reason: resolvedReason,
      message:
        resolvedReason === 'progress_unavailable'
          ? PROGRESS_UNAVAILABLE_MESSAGE
          : NOT_COUNTED_MESSAGE,
    };
  }
  return {
    ok: true,
    submitted: true,
    assignment_id: assignmentId,
    attempt_id: attemptId,
    official_score: score,
    reason: '',
    message: score == null ? '已提交' : `已提交，官方分 ${score}`,
  };
}

export async function postStudentSubmit(input: {
  apiBase: string;
  studentId: string;
  assignmentId: string;
  files: File[];
}): Promise<StudentSubmitResult> {
  const form = new FormData();
  form.set('student_id', input.studentId);
  form.set('assignment_id', input.assignmentId);
  for (const file of input.files) form.append('files', file);
  const res = await fetch(`${input.apiBase}/student/submit`, { method: 'POST', body: form });
  let payload: unknown = null;
  try {
    payload = await res.json();
  } catch {
    payload = { ok: false };
  }
  return parseStudentSubmitResponse(payload, res.status);
}
