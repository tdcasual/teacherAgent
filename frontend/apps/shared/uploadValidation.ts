const ONE_MB = 1024 * 1024

export const CHAT_ATTACHMENT_MAX_FILE_BYTES = 10 * ONE_MB
export const CHAT_ATTACHMENT_ALLOWED_SUFFIXES = [
  '.md',
  '.markdown',
  '.pdf',
  '.png',
  '.jpg',
  '.jpeg',
  '.bmp',
  '.webp',
  '.xls',
  '.xlsx',
]

export const ASSIGNMENT_UPLOAD_MAX_FILES_PER_FIELD = 20
export const ASSIGNMENT_UPLOAD_MAX_FILE_BYTES = 20 * ONE_MB
export const ASSIGNMENT_UPLOAD_MAX_TOTAL_BYTES = 80 * ONE_MB
export const ASSIGNMENT_UPLOAD_ALLOWED_SUFFIXES = [
  '.pdf',
  '.png',
  '.jpg',
  '.jpeg',
  '.bmp',
  '.webp',
  '.md',
  '.markdown',
  '.txt',
  '.tex',
]

export const AVATAR_MAX_FILE_BYTES = 2 * ONE_MB
export const AVATAR_ALLOWED_SUFFIXES = ['.png', '.jpg', '.jpeg', '.webp']

type ValidateFilesOptions = {
  label: string
  maxCount?: number
  maxFileBytes?: number
  maxTotalBytes?: number
  allowedSuffixes?: string[]
}

const formatBytesLimit = (bytes: number): string => {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0B'
  if (bytes % ONE_MB === 0) return `${bytes / ONE_MB}MB`
  const kb = Math.round(bytes / 1024)
  return `${kb}KB`
}

const fileSuffix = (name: string): string => {
  const text = String(name || '').trim().toLowerCase()
  const idx = text.lastIndexOf('.')
  if (idx < 0 || idx === text.length - 1) return ''
  return text.slice(idx)
}

export const validateFilesBeforeUpload = (files: File[], options: ValidateFilesOptions): string => {
  const label = String(options.label || '文件')
  const selected = (files || []).filter(Boolean)
  if (!selected.length) return ''

  if (typeof options.maxCount === 'number' && options.maxCount > 0 && selected.length > options.maxCount) {
    return `${label}最多上传 ${options.maxCount} 个文件`
  }

  const allowed = Array.isArray(options.allowedSuffixes) && options.allowedSuffixes.length
    ? new Set(options.allowedSuffixes.map((item) => String(item || '').trim().toLowerCase()).filter(Boolean))
    : null

  let total = 0
  for (const file of selected) {
    const size = Number(file.size || 0)
    total += Math.max(0, size)
    if (typeof options.maxFileBytes === 'number' && options.maxFileBytes > 0 && size > options.maxFileBytes) {
      return `${label}中单个文件大小不能超过 ${formatBytesLimit(options.maxFileBytes)}`
    }
    if (allowed) {
      const suffix = fileSuffix(file.name)
      if (!suffix || !allowed.has(suffix)) {
        return `${label}包含不支持的文件类型: ${suffix || file.name}`
      }
    }
  }

  if (typeof options.maxTotalBytes === 'number' && options.maxTotalBytes > 0 && total > options.maxTotalBytes) {
    return `${label}总大小不能超过 ${formatBytesLimit(options.maxTotalBytes)}`
  }

  return ''
}

export const validateAvatarFileBeforeUpload = (file: File | null): string => {
  if (!file) return '请先选择头像文件'
  return validateFilesBeforeUpload([file], {
    label: '头像文件',
    maxCount: 1,
    maxFileBytes: AVATAR_MAX_FILE_BYTES,
    allowedSuffixes: AVATAR_ALLOWED_SUFFIXES,
  })
}
