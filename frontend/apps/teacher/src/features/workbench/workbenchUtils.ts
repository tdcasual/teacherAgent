export const parseCommaList = (text: string) =>
  String(text || '')
    .split(/[，,]/g)
    .map((s) => s.trim())
    .filter(Boolean)

export const parseLineList = (text: string) =>
  String(text || '')
    .split(/\n/g)
    .map((s) => s.trim())
    .filter(Boolean)

export const difficultyOptions = [
  { value: 'basic', label: '基础' },
  { value: 'medium', label: '中等' },
  { value: 'advanced', label: '较难' },
  { value: 'challenge', label: '压轴' },
] as const

export const normalizeDifficulty = (value: any) => {
  const raw = String(value || '').trim()
  if (!raw) return 'basic'
  const v = raw.toLowerCase()
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
    'very_hard': 'challenge',
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
  }
  if (mapping[v]) return mapping[v]
  for (const [k, norm] of Object.entries(mapping)) {
    if (k && raw.includes(k)) return norm
  }
  return 'basic'
}

export const difficultyLabel = (value: any) => {
  const norm = normalizeDifficulty(value)
  const found = difficultyOptions.find((opt) => opt.value === norm)
  return found ? found.label : '基础'
}

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
}

export const formatMissingRequirements = (missing?: string[]) => {
  const items = Array.isArray(missing) ? missing : []
  return items.map((key) => requirementLabels[key] || key).join('、')
}

