import type { AssignmentKind, ContentSource } from '../../appTypes';

export const parseCommaList = (text: string) =>
  String(text || '')
    .split(/[，,]/g)
    .map((s) => s.trim())
    .filter(Boolean);

export const parseLineList = (text: string) =>
  String(text || '')
    .split(/\n/g)
    .map((s) => s.trim())
    .filter(Boolean);

export const difficultyOptions = [
  { value: 'basic', label: '基础' },
  { value: 'medium', label: '中等' },
  { value: 'advanced', label: '较难' },
  { value: 'challenge', label: '压轴' },
] as const;

export const normalizeDifficulty = (value: unknown) => {
  const raw = String(value || '').trim();
  if (!raw) return 'basic';
  const v = raw.toLowerCase();
  const mapping: Record<string, string> = {
    basic: 'basic',
    medium: 'medium',
    advanced: 'advanced',
    challenge: 'challenge',
    easy: 'basic',
    intermediate: 'medium',
    hard: 'advanced',
    expert: 'challenge',
    'very hard': 'challenge',
    very_hard: 'challenge',
    入门: 'basic',
    简单: 'basic',
    基础: 'basic',
    中等: 'medium',
    一般: 'medium',
    提高: 'medium',
    较难: 'advanced',
    困难: 'advanced',
    拔高: 'advanced',
    压轴: 'challenge',
    挑战: 'challenge',
  };
  if (mapping[v]) return mapping[v];
  for (const [k, norm] of Object.entries(mapping)) {
    if (k && raw.includes(k)) return norm;
  }
  return 'basic';
};

export const difficultyLabel = (value: unknown) => {
  const norm = normalizeDifficulty(value);
  const found = difficultyOptions.find((opt) => opt.value === norm);
  return found ? found.label : '基础';
};

const requirementLabels: Record<string, string> = {
  subject: '学科',
  topic: '主题',
  grade_level: '年级',
  class_level: '班级水平',
  core_concepts: '核心概念',
  typical_problem: '典型题型/例题',
  misconceptions: '易错点/易混点',
  duration_minutes: '作业时间',
  preferences: '作业偏好',
  extra_constraints: '额外限制',
  brief: '作业说明',
  discussion_goals: '讨论目标',
};

export const formatMissingRequirements = (missing?: string[]) => {
  const items = Array.isArray(missing) ? missing : [];
  return items.map((key) => requirementLabels[key] || key).join('、');
};

export const ASSIGNMENT_KIND_OPTIONS = [
  { value: 'problem_set', label: '做题作业' },
  { value: 'scenario', label: '情景作业' },
  { value: 'science_history', label: '科学史作业' },
  { value: 'practical', label: '实践作业' },
] as const;

export const CONTENT_SOURCE_OPTIONS = [
  { value: 'upload', label: '上传文件' },
  { value: 'bank', label: '题库选题' },
  { value: 'ai', label: 'AI 起草' },
] as const;

export const BANK_SOURCE_DISABLED_TITLE = '题库仅用于做题作业';

export const computeLocalRequirementsMissing = (
  req: Record<string, unknown> | undefined,
  assignmentKind = 'problem_set',
) => {
  const missing: string[] = [];
  const subject = String(req?.subject || '').trim();
  const topic = String(req?.topic || '').trim();
  const grade = String(req?.grade_level || '').trim();
  if (!subject) missing.push('subject');
  if (!topic) missing.push('topic');
  if (!grade) missing.push('grade_level');
  if (assignmentKind !== 'problem_set') {
    if (!String(req?.brief || '').trim()) missing.push('brief');
    return missing;
  }
  const classLevel = String(req?.class_level || '').trim();
  const core = Array.isArray(req?.core_concepts) ? req.core_concepts : [];
  const typical = String(req?.typical_problem || '').trim();
  const misconceptions = Array.isArray(req?.misconceptions) ? req.misconceptions : [];
  const duration = Number(req?.duration_minutes || 0);
  const prefs = Array.isArray(req?.preferences) ? req.preferences : [];
  if (!['偏弱', '中等', '较强', '混合'].includes(classLevel)) missing.push('class_level');
  if (core.filter(Boolean).length < 3) missing.push('core_concepts');
  if (!typical) missing.push('typical_problem');
  if (misconceptions.filter(Boolean).length < 4) missing.push('misconceptions');
  if (![20, 40, 60].includes(duration)) missing.push('duration_minutes');
  if (prefs.filter(Boolean).length < 1) missing.push('preferences');
  return missing;
};

export const clampQuestionCount = (raw: unknown, fallback = 5) => {
  const value = Number(raw);
  if (!Number.isFinite(value)) return fallback;
  return Math.min(20, Math.max(1, Math.round(value)));
};

export const isAssignmentKind = (value: unknown): value is AssignmentKind =>
  value === 'problem_set' ||
  value === 'scenario' ||
  value === 'science_history' ||
  value === 'practical';

export const isContentSource = (value: unknown): value is ContentSource =>
  value === 'upload' || value === 'bank' || value === 'ai';
