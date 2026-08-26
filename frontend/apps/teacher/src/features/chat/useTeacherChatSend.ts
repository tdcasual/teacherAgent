import { useCallback, type Dispatch, type MutableRefObject, type SetStateAction } from 'react'
import { stripTransientPendingBubbles } from './pendingOverlay'
import { parseInvocationInput } from './invocation'
import { decideSkillRouting } from './requestRouting'
import {
  buildAnalysisTargetContextMessage,
  buildAnalysisTargetContract,
} from './useTeacherChatApiHelpers'
import { toUserFacingErrorMessage } from '../../../../shared/errorMessage'
import { readTeacherAuthSubject } from '../auth/teacherAuth'
import { makeId } from '../../utils/id'
import { nowTime } from '../../utils/time'
import type {
  ChatStartResult,
  ExecutionTimelineEntry,
  Message,
  PendingChatJob,
  PendingToolRun,
  Skill,
  WheelScrollZone,
} from '../../appTypes'
import type { AnalysisReportSummary } from '../../types/workflow'

const toErrorMessage = (error: unknown, fallback = '请求失败') => {
  return toUserFacingErrorMessage(error, fallback)
}

export type UseTeacherChatSendParams = {
  apiBase: string
  authToken: string
  pendingChatJob: PendingChatJob | null
  pendingChatJobRef: MutableRefObject<PendingChatJob | null>
  skillList: Skill[]
  activeSkillId: string
  skillPinned: boolean
  activeSessionId: string
  messages: Message[]
  selectedAnalysisTarget?: AnalysisReportSummary | null
  setComposerWarning: Dispatch<SetStateAction<string>>
  chooseSkill: (skillId: string, pinned?: boolean) => void
  setActiveSessionId: Dispatch<SetStateAction<string>>
  setWheelScrollZone: (zone: WheelScrollZone) => void
  enableAutoScroll: () => void
  setMessages: Dispatch<SetStateAction<Message[]>>
  setInput: Dispatch<SetStateAction<string>>
  setSending: Dispatch<SetStateAction<boolean>>
  setChatQueueHint: Dispatch<SetStateAction<string>>
  setPendingStreamStage: Dispatch<SetStateAction<string>>
  setPendingToolRuns: Dispatch<SetStateAction<PendingToolRun[]>>
  setExecutionTimeline: Dispatch<SetStateAction<ExecutionTimelineEntry[]>>
  setPendingChatJob: Dispatch<SetStateAction<PendingChatJob | null>>
}

export function useTeacherChatSend(params: UseTeacherChatSendParams) {
  const {
    apiBase,
    authToken,
    pendingChatJob,
    pendingChatJobRef,
    skillList,
    activeSkillId,
    skillPinned,
    activeSessionId,
    messages,
    selectedAnalysisTarget,
    setComposerWarning,
    chooseSkill,
    setActiveSessionId,
    setWheelScrollZone,
    enableAutoScroll,
    setMessages,
    setInput,
    setSending,
    setChatQueueHint,
    setPendingStreamStage,
    setPendingToolRuns,
    setExecutionTimeline,
    setPendingChatJob,
  } = params

  const submitMessage = useCallback(
    async (inputText: string, options?: { attachments?: Array<{ attachment_id: string }> }) => {
      if (!authToken) {
        setComposerWarning('请先在顶部完成教师认证。')
        return false
      }
      if (pendingChatJob?.job_id) return false
      const attachmentRefs = Array.isArray(options?.attachments)
        ? options?.attachments.filter((item) => String(item?.attachment_id || '').trim())
        : []
      const trimmed = inputText.trim()
      if (!trimmed && attachmentRefs.length === 0) return false
      const parsedInvocation = parseInvocationInput(trimmed, {
        knownSkillIds: skillList.map((item) => item.id),
        activeSkillId: activeSkillId || 'physics-teacher-ops',
      })
      let cleanedText = parsedInvocation.cleanedInput.trim()
      if (!cleanedText && attachmentRefs.length > 0) {
        cleanedText = '请阅读我上传的附件并回答。'
      }
      if (!cleanedText) {
        setComposerWarning('请在召唤后补充问题内容。')
        return false
      }
      const routingDecision = decideSkillRouting({
        parsedInvocation,
        activeSkillId,
        skillPinned,
      })
      if (routingDecision.normalizedWarnings.length) {
        setComposerWarning(routingDecision.normalizedWarnings.join('；'))
      } else {
        setComposerWarning('')
      }
      if (routingDecision.shouldPinEffectiveSkill && parsedInvocation.effectiveSkillId) {
        chooseSkill(parsedInvocation.effectiveSkillId, true)
      }
      const sessionId = activeSessionId || 'main'
      if (!activeSessionId) setActiveSessionId(sessionId)
      const requestId = `tchat_${Date.now()}_${Math.random().toString(16).slice(2)}`
      const placeholderId = `asst_${Date.now()}_${Math.random().toString(16).slice(2)}`
      const teacherId = String(readTeacherAuthSubject()?.teacher_id || '').trim()
      setWheelScrollZone('chat')
      enableAutoScroll()
      setMessages((prev) => {
        const next = stripTransientPendingBubbles(prev)
        return [
          ...next,
          { id: makeId(), role: 'user' as const, content: cleanedText, time: nowTime() },
          { id: placeholderId, role: 'assistant' as const, content: '正在生成…', time: nowTime() },
        ]
      })
      setInput('')
      const analysisTarget = buildAnalysisTargetContract(selectedAnalysisTarget)
      const analysisTargetContext = buildAnalysisTargetContextMessage(selectedAnalysisTarget)
      const contextSeed = analysisTargetContext
        ? [...messages, { id: 'analysis_target', role: 'assistant' as const, content: analysisTargetContext, time: '' }]
        : [...messages]
      const contextMessages = [...contextSeed, { id: 'temp', role: 'user' as const, content: cleanedText, time: '' }]
        .slice(-40)
        .map((msg) => ({ role: msg.role, content: msg.content }))
      setSending(true)
      setExecutionTimeline([])
      try {
        const res = await fetch(`${apiBase}/chat/start`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            request_id: requestId,
            session_id: sessionId,
            messages: contextMessages,
            role: 'teacher',
            teacher_id: teacherId || undefined,
            skill_id: routingDecision.skillIdForRequest,
            attachments: attachmentRefs.length ? attachmentRefs : undefined,
            analysis_target: analysisTarget || undefined,
          }),
        })
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || `状态码 ${res.status}`)
        }
        const data = (await res.json()) as ChatStartResult
        if (!data?.job_id) throw new Error('任务编号缺失')
        const runtimeWarnings = Array.isArray(data.warnings)
          ? data.warnings.map((item) => String(item || '').trim()).filter(Boolean)
          : []
        if (runtimeWarnings.length) {
          setComposerWarning(runtimeWarnings.join('；'))
        }
        const lanePos = Number(data.lane_queue_position || 0)
        const laneSize = Number(data.lane_queue_size || 0)
        setChatQueueHint(lanePos > 0 ? `排队中，前方 ${lanePos} 条（队列 ${laneSize}）` : '处理中...')
        const nextPendingJob: PendingChatJob = {
          job_id: data.job_id,
          request_id: requestId,
          placeholder_id: placeholderId,
          user_text: cleanedText,
          session_id: sessionId,
          lane_id: data.lane_id,
          created_at: Date.now(),
        }
        pendingChatJobRef.current = nextPendingJob
        setPendingChatJob(nextPendingJob)
        setPendingStreamStage('排队中...')
        setPendingToolRuns([])
        return true
      } catch (err: unknown) {
        const errorMessage = toErrorMessage(err)
        setMessages((prev) =>
          prev.map((m) =>
            m.id === placeholderId
              ? { ...m, content: `抱歉，请求失败：${errorMessage}`, time: nowTime() }
              : m,
          ),
        )
        setSending(false)
        setChatQueueHint('')
        setPendingStreamStage('')
        setPendingToolRuns([])
        pendingChatJobRef.current = null
        setPendingChatJob(null)
        return false
      }
    },
    [
      pendingChatJob?.job_id, skillList, activeSkillId, skillPinned, activeSessionId, messages, apiBase,
      authToken, selectedAnalysisTarget, pendingChatJobRef,
      setComposerWarning, chooseSkill, setActiveSessionId, setWheelScrollZone, enableAutoScroll,
      setMessages, setInput, setSending, setChatQueueHint, setPendingStreamStage, setPendingToolRuns, setExecutionTimeline, setPendingChatJob,
    ],
  )

  return { submitMessage }
}
