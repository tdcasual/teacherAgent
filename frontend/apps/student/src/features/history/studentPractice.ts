import { toUserFacingErrorMessage } from '../../../../shared/errorMessage';
import { BANK_MISS_COPY } from '../../assignmentKind';

export type StudentPracticeResult = {
  ok: boolean;
  bankMiss: boolean;
  practice_id: string;
  message: string;
};

const asRecord = (value: unknown): Record<string, unknown> =>
  value && typeof value === 'object' ? (value as Record<string, unknown>) : {};

const detailOf = (payload: unknown): string => {
  const record = asRecord(payload);
  const detail = record.detail;
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail === 'object') {
    const nested = asRecord(detail);
    if (typeof nested.error === 'string') return nested.error;
    if (typeof nested.detail === 'string') return nested.detail;
  }
  if (typeof record.error === 'string') return record.error;
  return '';
};

export async function postStudentPractice(input: {
  apiBase: string;
  assignmentId: string;
}): Promise<StudentPracticeResult> {
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
  const detail = detailOf(payload);
  const bankMiss = detail === 'question_bank_insufficient';
  if (bankMiss) {
    return { ok: false, bankMiss: true, practice_id: '', message: BANK_MISS_COPY };
  }
  const record = asRecord(payload);
  if (!res.ok || record.ok === false) {
    return {
      ok: false,
      bankMiss: false,
      practice_id: '',
      message: toUserFacingErrorMessage(
        payload ?? `状态码 ${res.status}`,
        '补练失败，请稍后重试。',
      ),
    };
  }
  return {
    ok: true,
    bankMiss: false,
    practice_id: String(record.practice_id || '').trim(),
    message: '补练已布置',
  };
}
