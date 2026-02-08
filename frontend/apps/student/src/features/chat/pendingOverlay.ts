type MessageLike = {
  id: string
  role: string
  content: string
}

const pendingStatusTexts = new Set(['正在生成…', '正在恢复上一条回复…'])

export const stripTransientPendingBubbles = <T extends MessageLike>(messages: T[]): T[] => {
  return messages.filter((msg) => {
    if (msg.role !== 'assistant') return true
    if (!pendingStatusTexts.has(String(msg.content || '').trim())) return true
    return !(String(msg.id || '').startsWith('asst_') || String(msg.id || '').startsWith('pending_'))
  })
}

