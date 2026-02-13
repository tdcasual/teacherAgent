const FALLBACK_NETWORK_ERROR = '网络异常，请稍后重试。'
const FALLBACK_SERVER_ERROR = '服务暂时不可用，请稍后重试。'

const ERROR_CODE_MESSAGES: Record<string, string> = {
  avatar_too_large: '上传文件过大，请压缩后重试。',
  avatar_empty: '上传文件为空，请重新选择。',
  avatar_invalid_extension: '文件格式不支持，请上传允许的图片类型。',
  avatar_svg_not_allowed: 'SVG 格式不支持，请更换图片格式。',
  invalid_credential: '认证失败，请检查凭据后重试。',
  locked: '尝试次数过多，请稍后再试。',
  token_expired: '登录已过期，请重新登录。',
  token_revoked: '登录已失效，请重新登录。',
  missing_authorization: '请先登录后再操作。',
  forbidden_chat_job: '当前账号无权访问该任务。',
  forbidden_teacher_scope: '当前账号无权访问该教师资源。',
  forbidden_student_scope: '当前账号无权访问该学生资源。',
}

const DANGEROUS_MESSAGE_RE = /[<>{}`]/
const INTERNAL_DETAIL_RE = /(traceback|exception|stack|sql|select\s|insert\s|delete\s|node_modules|http:\/\/|https:\/\/)/i

const asRecord = (value: unknown): Record<string, unknown> | null => {
  if (!value || typeof value !== 'object') return null
  return value as Record<string, unknown>
}

const normalizeCode = (value: unknown): string => String(value || '').trim().toLowerCase()

const sanitizePlainMessage = (message: string, fallback: string): string => {
  const text = String(message || '').trim()
  if (!text) return fallback
  const mapped = ERROR_CODE_MESSAGES[normalizeCode(text)]
  if (mapped) return mapped
  if (text.length > 160) return fallback
  if (DANGEROUS_MESSAGE_RE.test(text)) return fallback
  if (INTERNAL_DETAIL_RE.test(text)) return fallback
  return text
}

const parseJsonIfPossible = (text: string): unknown => {
  const trimmed = text.trim()
  if (!trimmed) return null
  if (!trimmed.startsWith('{') && !trimmed.startsWith('[')) return null
  try {
    return JSON.parse(trimmed)
  } catch {
    return null
  }
}

export const toUserFacingErrorMessage = (error: unknown, fallback = FALLBACK_NETWORK_ERROR): string => {
  if (error instanceof Error) {
    return toUserFacingErrorMessage(error.message, fallback)
  }
  if (typeof error === 'string') {
    const parsed = parseJsonIfPossible(error)
    if (parsed != null) return toUserFacingErrorMessage(parsed, fallback)
    return sanitizePlainMessage(error, fallback)
  }
  if (Array.isArray(error)) {
    for (const item of error) {
      const next = toUserFacingErrorMessage(item, '')
      if (next) return next
    }
    return fallback
  }
  const record = asRecord(error)
  if (!record) return fallback

  const detail = record.detail
  if (detail !== undefined) {
    const next = toUserFacingErrorMessage(detail, '')
    if (next) return next
  }
  const code = normalizeCode(record.error)
  if (code && ERROR_CODE_MESSAGES[code]) return ERROR_CODE_MESSAGES[code]
  if (typeof record.message === 'string') {
    const next = sanitizePlainMessage(record.message, '')
    if (next) return next
  }
  if (code) return sanitizePlainMessage(code, fallback)
  return fallback
}

export const readHttpErrorMessage = async (res: Response, fallback = FALLBACK_NETWORK_ERROR): Promise<string> => {
  let body = ''
  try {
    body = await res.text()
  } catch {
    // ignore read failures
  }
  const baseFallback = res.status >= 500 ? FALLBACK_SERVER_ERROR : fallback
  if (!body) return baseFallback
  return toUserFacingErrorMessage(body, baseFallback)
}
