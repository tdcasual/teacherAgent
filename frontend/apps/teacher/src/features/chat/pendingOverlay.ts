import { nowTime, timeFromIso } from '../../utils/time'

type Message = {
  id: string
  role: 'user' | 'assistant'
  content: string
  time: string
}

type PendingChatJob = {
  job_id: string
  placeholder_id: string
  user_text: string
  session_id: string
  created_at: number
}

const pendingUserMessageId = (jobId: string) => `pending_user_${jobId}`
const pendingStatusTexts = new Set(['正在生成…', '正在恢复上一条回复…'])

export const stripTransientPendingBubbles = (messages: Message[]): Message[] => {
  return messages.filter((msg) => {
    if (msg.role !== 'assistant') return true
    if (!pendingStatusTexts.has(String(msg.content || '').trim())) return true
    return !(msg.id.startsWith('asst_') || msg.id.startsWith('pending_'))
  })
}

export const withPendingChatOverlay = (messages: Message[], pending: PendingChatJob | null, targetSessionId: string): Message[] => {
  const base = stripTransientPendingBubbles(messages)
  if (!pending?.job_id || pending.session_id !== targetSessionId) return base
  if (base.some((msg) => msg.id === pending.placeholder_id)) return base

  const next = [...base]
  const hasUserText = pending.user_text
    ? next.some((msg) => msg.role === 'user' && msg.content === pending.user_text)
    : true
  if (!hasUserText && pending.user_text) {
    next.push({
      id: pendingUserMessageId(pending.job_id),
      role: 'user',
      content: pending.user_text,
      time: timeFromIso(new Date(pending.created_at).toISOString()),
    })
  }
  next.push({
    id: pending.placeholder_id,
    role: 'assistant',
    content: '正在生成…',
    time: nowTime(),
  })
  return next
}
