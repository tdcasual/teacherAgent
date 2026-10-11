export type AssignmentKind = 'problem_set' | 'scenario' | 'science_history' | 'practical';

export const COACH_NOT_SUBMIT_HINT = '聊天是陪练，不是提交';
export const BANK_MISS_COPY = '题库不足';

export const isAssignmentKind = (value: unknown): value is AssignmentKind =>
  value === 'problem_set' ||
  value === 'scenario' ||
  value === 'science_history' ||
  value === 'practical';

export const coerceAssignmentKind = (value: unknown): AssignmentKind =>
  isAssignmentKind(value) ? value : 'problem_set';

export const parseAllowPractice = (value: unknown, kind: AssignmentKind): boolean => {
  if (kind !== 'problem_set') return false;
  if (value === undefined || value === null || value === '') return true;
  return Boolean(value);
};

export const canOfferPractice = (input: {
  assignment_kind?: string;
  allow_practice?: boolean;
  submitted?: boolean;
}): boolean =>
  coerceAssignmentKind(input.assignment_kind) === 'problem_set' &&
  Boolean(input.allow_practice) &&
  Boolean(input.submitted);

export const submitActionLabel = (kind?: string): string => {
  const resolved = coerceAssignmentKind(kind);
  if (resolved === 'practical') return '提交实践照片';
  if (resolved === 'scenario' || resolved === 'science_history') return '提交书面/照片';
  return '提交作业';
};

export const submitSuccessCopy = (
  kind: string | undefined,
  officialScore: number | null,
): string => {
  const resolved = coerceAssignmentKind(kind);
  if (resolved === 'practical') return '实践照片已交';
  if (resolved === 'scenario' || resolved === 'science_history') return '书面/照片已交';
  return officialScore == null ? '已提交' : `已提交，官方分 ${officialScore}`;
};
