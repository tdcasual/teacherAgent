export type InvocationTriggerType = 'skill'

export type InvocationToken = {
  type: InvocationTriggerType
  id: string
  start: number
  end: number
}

export type InvocationTrigger = {
  type: InvocationTriggerType
  start: number
  query: string
}

export type ParseInvocationOptions = {
  knownSkillIds: string[]
  activeSkillId: string
}

export type ParsedInvocation = {
  cleanedInput: string
  requestedSkillId: string
  effectiveSkillId: string
  warnings: string[]
  tokens: InvocationToken[]
}

const TOKEN_REGEX = /(^|\s)(\$)([^\s@$]+)/g
const TRIGGER_REGEX = /(?:^|\s)(\$)([^\s@$]*)$/
const INVOCATION_ID_REGEX = /^[A-Za-z0-9_-]{1,80}$/

const normalizeIdList = (ids: string[]) => {
  const next = new Set<string>()
  for (const raw of ids || []) {
    const id = String(raw || '').trim()
    if (id) next.add(id)
  }
  return next
}

const ensureInvocationId = (raw: string) => {
  const id = String(raw || '').trim()
  return INVOCATION_ID_REGEX.test(id) ? id : ''
}

export const buildInvocationToken = (type: InvocationTriggerType, id: string) => {
  if (type !== 'skill') return ''
  const clean = ensureInvocationId(id)
  if (!clean) return ''
  return `$${clean}`
}

const removeTokenRanges = (input: string, tokens: InvocationToken[]) => {
  if (!tokens.length) return input.trim()
  const ranges = [...tokens].sort((a, b) => a.start - b.start)
  let pos = 0
  let out = ''
  for (const range of ranges) {
    out += input.slice(pos, range.start)
    pos = range.end
  }
  out += input.slice(pos)
  return out.replace(/\s+/g, ' ').trim()
}

export const parseInvocationInput = (input: string, options: ParseInvocationOptions): ParsedInvocation => {
  const source = String(input || '')
  const knownSkills = normalizeIdList(options.knownSkillIds || [])
  const warnings: string[] = []
  const tokens: InvocationToken[] = []

  TOKEN_REGEX.lastIndex = 0
  let match = TOKEN_REGEX.exec(source)
  while (match) {
    const prefix = match[1] || ''
    const sigil = match[2] || ''
    const rawId = match[3] || ''
    const id = ensureInvocationId(rawId)
    const start = match.index + prefix.length
    const end = start + 1 + rawId.length
    if (!id) {
      warnings.push(`无效召唤标识：${sigil}${rawId}`)
      match = TOKEN_REGEX.exec(source)
      continue
    }
    tokens.push({ type: 'skill', id, start, end })
    match = TOKEN_REGEX.exec(source)
  }

  const requestedSkillId = [...tokens].reverse().find((token) => token.type === 'skill')?.id || ''

  let effectiveSkillId = ensureInvocationId(options.activeSkillId) || ''
  if (requestedSkillId) {
    if (knownSkills.has(requestedSkillId)) {
      effectiveSkillId = requestedSkillId
    } else {
      warnings.push(`未识别的技能：$${requestedSkillId}，已使用 ${effectiveSkillId || '默认技能'}`)
    }
  }

  return {
    cleanedInput: removeTokenRanges(source, tokens),
    requestedSkillId,
    effectiveSkillId,
    warnings,
    tokens,
  }
}

export const findInvocationTrigger = (input: string, cursorPos: number): InvocationTrigger | null => {
  const safeCursor = Math.max(0, Math.min(cursorPos, input.length))
  const uptoCursor = input.slice(0, safeCursor)
  const match = TRIGGER_REGEX.exec(uptoCursor)
  if (!match) return null
  const sigil = match[1] || ''
  const query = (match[2] || '').toLowerCase()
  const full = match[0] || ''
  const offset = full.lastIndexOf(sigil)
  const start = match.index + Math.max(0, offset)
  return { type: 'skill', start, query }
}
