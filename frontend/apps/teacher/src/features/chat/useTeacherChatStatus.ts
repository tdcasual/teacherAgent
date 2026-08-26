import type { Dispatch, MutableRefObject, SetStateAction } from 'react'
import { startVisibilityAwareBackoffPolling } from '../../../../shared/visibilityBackoffPolling'
import { toUserFacingErrorMessage } from '../../../../shared/errorMessage'
import { nowTime } from '../../utils/time'
import { withPendingChatOverlay } from './pendingOverlay'
import type {
  ChatJobStatus,
  ExecutionTimelineEntry,
  Message,
  PendingChatJob,
  PendingToolRun,
} from '../../appTypes'

export const toTeacherChatErrorMessage = (error: unknown, fallback = '请求失败') => {
  return toUserFacingErrorMessage(error, fallback)
}

export const applyTeacherChatQueuedHints = (
  lanePos: number,
  laneSize: number,
  setChatQueueHint: Dispatch<SetStateAction<string>>,
  setPendingStreamStage: Dispatch<SetStateAction<string>>,
  idleHint = '排队中...',
) => {
  setChatQueueHint(lanePos > 0 ? `排队中，前方 ${lanePos} 条（队列 ${laneSize}）` : idleHint)
  setPendingStreamStage('排队中...')
}

export const applyTeacherChatProcessingHints = (
  setChatQueueHint: Dispatch<SetStateAction<string>>,
  setPendingStreamStage: Dispatch<SetStateAction<string>>,
) => {
  setChatQueueHint('处理中...')
  setPendingStreamStage('处理中...')
}

export type TeacherChatPendingJobHandlers = {
  setPlaceholderContent: (content: string) => void
  finishSuccess: (replyText: string) => void
  finishFailure: (message: string) => void
}

export const createTeacherChatPendingJobHandlers = (params: {
  pendingChatJob: PendingChatJob
  pendingChatJobRef: MutableRefObject<PendingChatJob | null>
  activeSessionId: string
  setMessages: Dispatch<SetStateAction<Message[]>>
  setPendingChatJob: Dispatch<SetStateAction<PendingChatJob | null>>
  setChatQueueHint: Dispatch<SetStateAction<string>>
  setPendingStreamStage: Dispatch<SetStateAction<string>>
  setPendingToolRuns: Dispatch<SetStateAction<PendingToolRun[]>>
  setSending: Dispatch<SetStateAction<boolean>>
  refreshTeacherSessions: () => Promise<void> | void
}): TeacherChatPendingJobHandlers => {
  const {
    pendingChatJob,
    pendingChatJobRef,
    activeSessionId,
    setMessages,
    setPendingChatJob,
    setChatQueueHint,
    setPendingStreamStage,
    setPendingToolRuns,
    setSending,
    refreshTeacherSessions,
  } = params
  const targetSessionId = activeSessionId || pendingChatJob.session_id || 'main'
  const sameSession =
    !pendingChatJob.session_id || !activeSessionId || pendingChatJob.session_id === activeSessionId
  const clearPendingUi = () => {
    pendingChatJobRef.current = null
    setPendingChatJob(null)
    setChatQueueHint('')
    setPendingStreamStage('')
    setPendingToolRuns([])
    setSending(false)
  }
  const setPlaceholderContent = (content: string) => {
    if (!sameSession) return
    setMessages((prev) => {
      const overlaid = withPendingChatOverlay(prev, pendingChatJob, targetSessionId)
      return overlaid.map((item) =>
        item.id === pendingChatJob.placeholder_id ? { ...item, content, time: nowTime() } : item,
      )
    })
  }
  const finishSuccess = (replyText: string) => {
    setMessages((prev) => {
      const overlaid = withPendingChatOverlay(prev, pendingChatJob, targetSessionId)
      return overlaid.map((item) =>
        item.id === pendingChatJob.placeholder_id ? { ...item, content: replyText || '已收到。', time: nowTime() } : item,
      )
    })
    clearPendingUi()
    void refreshTeacherSessions()
  }
  const finishFailure = (message: string) => {
    setMessages((prev) => {
      const overlaid = withPendingChatOverlay(prev, pendingChatJob, targetSessionId)
      return overlaid.map((item) =>
        item.id === pendingChatJob.placeholder_id
          ? { ...item, content: `抱歉，请求失败：${message || '请求失败'}`, time: nowTime() }
          : item,
      )
    })
    clearPendingUi()
  }
  return { setPlaceholderContent, finishSuccess, finishFailure }
}

export const fetchTeacherChatJobStatus = async (
  apiBase: string,
  jobId: string,
  signal?: AbortSignal,
): Promise<ChatJobStatus> => {
  const res = await fetch(`${apiBase}/chat/status?job_id=${encodeURIComponent(jobId)}`, { signal })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `状态码 ${res.status}`)
  }
  return (await res.json()) as ChatJobStatus
}

export const startTeacherChatStatusPolling = (params: {
  apiBase: string
  pendingChatJob: PendingChatJob
  activeSessionId: string
  finishSuccess: (replyText: string) => void
  finishFailure: (message: string) => void
  setPlaceholderContent: (content: string) => void
  setChatQueueHint: Dispatch<SetStateAction<string>>
  setPendingStreamStage: Dispatch<SetStateAction<string>>
  setExecutionTimeline: Dispatch<SetStateAction<ExecutionTimelineEntry[]>>
}): (() => void) => {
  const {
    apiBase,
    pendingChatJob,
    activeSessionId,
    finishSuccess,
    finishFailure,
    setPlaceholderContent,
    setChatQueueHint,
    setPendingStreamStage,
    setExecutionTimeline,
  } = params
  return startVisibilityAwareBackoffPolling(
    async ({ signal }) => {
      if (pendingChatJob.session_id && activeSessionId && pendingChatJob.session_id !== activeSessionId) {
        return 'continue'
      }
      const data = await fetchTeacherChatJobStatus(apiBase, pendingChatJob.job_id, signal)
      if (Array.isArray(data.execution_timeline)) {
        setExecutionTimeline(data.execution_timeline)
      }
      if (data.status === 'done') {
        finishSuccess(data.reply || '')
        return 'stop'
      }
      if (data.status === 'failed' || data.status === 'cancelled') {
        finishFailure(data.error_detail || data.error || '请求失败')
        return 'stop'
      }
      const lanePos = Number(data.lane_queue_position || 0)
      const laneSize = Number(data.lane_queue_size || 0)
      if (data.status === 'queued') {
        applyTeacherChatQueuedHints(lanePos, laneSize, setChatQueueHint, setPendingStreamStage)
      } else if (data.status === 'processing') {
        applyTeacherChatProcessingHints(setChatQueueHint, setPendingStreamStage)
      } else {
        setChatQueueHint('')
        setPendingStreamStage('')
      }
      return 'continue'
    },
    (err) => {
      const msg = toTeacherChatErrorMessage(err, '网络错误')
      setPlaceholderContent(`网络波动，正在重试…（${msg}）`)
    },
    { kickMode: 'direct', pollTimeoutMs: 15000, inFlightTimeoutMs: 20000 },
  )
}
