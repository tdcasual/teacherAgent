export const parseList = (value: string) =>
  value
    .split(/[，,\n]+/)
    .map((item) => item.trim())
    .filter(Boolean)

export const formatList = (items: string[]) => items.join('，')

export const boolMatchValue = (value: boolean | null | undefined) => {
  if (value === true) return 'true'
  if (value === false) return 'false'
  return 'any'
}

export const boolMatchFromValue = (value: string): boolean | undefined => {
  if (value === 'true') return true
  if (value === 'false') return false
  return undefined
}

export const formatTargetLabel = (provider?: string, mode?: string, model?: string) => {
  const text = [provider || '', mode || '', model || ''].map((item) => item.trim()).filter(Boolean).join(' / ')
  return text || '未配置'
}
