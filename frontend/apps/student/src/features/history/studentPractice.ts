import { toUserFacingErrorMessage } from '../../../../shared/errorMessage';

export async function postStudentPractice(input: {
  apiBase: string;
  assignmentId: string;
}): Promise<string> {
  const res = await fetch(
    `${input.apiBase}/student/assignment/${encodeURIComponent(input.assignmentId)}/practice`,
    { method: 'POST' },
  );
  let payload: unknown = null;
  try {
    payload = await res.json();
  } catch {
    payload = null;
  }
  const record = payload && typeof payload === 'object' ? (payload as Record<string, unknown>) : {};
  if (res.ok && record.ok !== false) return '补练已布置';
  return toUserFacingErrorMessage(payload ?? `状态码 ${res.status}`, '补练失败，请稍后重试。');
}
