import { useCallback, type FormEvent, type MutableRefObject } from 'react'
import { makeId } from '../../../../shared/id'
import { safeLocalStorageGetItem, safeLocalStorageRemoveItem, safeLocalStorageSetItem } from '../../../../shared/storage'
import { nowTime } from '../../../../shared/time'
import type { AssignmentDetail, ChatStartResult, Message, PendingChatJob, VerifiedStudent } from '../../appTypes'
import { stripTransientPendingBubbles } from './pendingOverlay'
import { parsePendingChatJobFromStorage } from './pendingChatJob'
import { withStudentSendLock } from './sendLock'

type UseStudentSendFlowParams = {
  apiBase: string
  input: string
  messages: Message[]
  activeSessionId: string
  todayAssignment: AssignmentDetail | null
  verifiedStudent: VerifiedStudent | null
  pendingChatJob: PendingChatJob | null
  attachments: Array<{ attachment_id: string }>
  activePersonaId?: string
  pendingChatKeyPrefix: string
  todayDate: () => string
  onSendSuccess: () => void

  setVerifyError: (value: string) => void
  setVerifyOpen: (value: boolean) => void
  setSending: (value: boolean) => void
  setInput: (value: string) => void
  setActiveSession: (sessionId: string) => void
  setPendingChatJob: (value: PendingChatJob | null) => void
  setMessages: (value: Message[] | ((prev: Message[]) => Message[])) => void
  updateMessage: (id: string, patch: Partial<Message>) => void

  pendingRecoveredFromStorageRef: MutableRefObject<boolean>
  skipAutoSessionLoadIdRef: MutableRefObject<string>
}

const toErrorMessage = (error: unknown, fallback = '请求失败') => {
  if (error instanceof Error) {
    const message = error.message.trim()
    if (message) return message
  }
  const raw = String(error || '').trim()
  return raw || fallback
}

export function useStudentSendFlow(params: UseStudentSendFlowParams) {
  const {
    apiBase,
    input,
    messages,
    activeSessionId,
    todayAssignment,
    verifiedStudent,
    pendingChatJob,
    attachments,
    activePersonaId,
    pendingChatKeyPrefix,
    todayDate,
    onSendSuccess,
    setVerifyError,
    setVerifyOpen,
    setSending,
    setInput,
    setActiveSession,
    setPendingChatJob,
    setMessages,
    updateMessage,
    pendingRecoveredFromStorageRef,
    skipAutoSessionLoadIdRef,
  } = params

  const handleSend = useCallback(
    async (event: FormEvent) => {
      event.preventDefault()
      if (!verifiedStudent) {
        setVerifyError('请先填写姓名并完成验证。')
        setVerifyOpen(true)
        return
      }
      if (pendingChatJob?.job_id) return
      const trimmed = input.trim()
      const attachmentRefs = attachments.filter((item) => String(item.attachment_id || '').trim())
      if (!trimmed && attachmentRefs.length === 0) return
      const userText = trimmed || '请阅读我上传的附件并回答。'

      const studentId = verifiedStudent.student_id
      const pendingKey = `${pendingChatKeyPrefix}${studentId}`

      const clearPendingFromStorage = () => {
        safeLocalStorageRemoveItem(pendingKey)
        pendingRecoveredFromStorageRef.current = false
        setPendingChatJob(null)
        setSending(false)
      }

      const syncPendingFromStorage = async ({ verifyRemote = false }: { verifyRemote?: boolean } = {}) => {
        const raw = safeLocalStorageGetItem(pendingKey)
        if (!raw) {
          pendingRecoveredFromStorageRef.current = false
          setPendingChatJob(null)
          setSending(false)
          return false
        }
        const parsed = parsePendingChatJobFromStorage(raw)
        if (!parsed) {
          clearPendingFromStorage()
          return false
        }

        if (verifyRemote) {
          try {
            const statusRes = await fetch(`${apiBase}/chat/status?job_id=${encodeURIComponent(parsed.job_id)}`)
            if (statusRes.status === 404) {
              clearPendingFromStorage()
              return false
            }
          } catch {
            // Keep the recovered pending record on transient status-check failures.
          }
        }

        pendingRecoveredFromStorageRef.current = true
        setPendingChatJob(parsed)
        setSending(false)
        return true
      }

      const waitPendingSync = async (timeoutMs = 2500) => {
        if (typeof window === 'undefined') return false
        setSending(true)
        const started = Date.now()
        while (Date.now() - started < timeoutMs) {
          if (await syncPendingFromStorage()) return true
          await new Promise((resolve) => window.setTimeout(resolve, 80))
        }
        setSending(false)
        return false
      }

      let startedSubmission = false

      const lockAcquired = await withStudentSendLock(studentId, async () => {
        if (await syncPendingFromStorage({ verifyRemote: true })) return

        startedSubmission = true
        const sessionId = activeSessionId || todayAssignment?.assignment_id || `general_${todayDate()}`
        if (!activeSessionId) setActiveSession(sessionId)
        const requestId = `schat_${studentId}_${Date.now()}_${Math.random().toString(16).slice(2)}`
        const placeholderId = `asst_${Date.now()}_${Math.random().toString(16).slice(2)}`

        setMessages((prev) => {
          const next = stripTransientPendingBubbles(prev)
          return [
            ...next,
            { id: makeId(), role: 'user', content: userText, time: nowTime() },
            { id: placeholderId, role: 'assistant', content: '正在生成…', time: nowTime() },
          ]
        })
        setInput('')

        const contextMessages = [...messages, { id: 'temp', role: 'user' as const, content: userText, time: '' }]
          .slice(-40)
          .map((msg) => ({ role: msg.role, content: msg.content }))

        setSending(true)
        try {
          const inferredAssignmentId =
            sessionId && !sessionId.startsWith('general_')
              ? sessionId
              : todayAssignment?.assignment_id && sessionId === todayAssignment.assignment_id
                ? todayAssignment.assignment_id
                : undefined
          const res = await fetch(`${apiBase}/chat/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              request_id: requestId,
              session_id: sessionId,
              messages: contextMessages,
              role: 'student',
              student_id: studentId,
              persona_id: activePersonaId || undefined,
              assignment_id: inferredAssignmentId,
              assignment_date: todayDate(),
              attachments: attachmentRefs.length ? attachmentRefs : undefined,
            }),
          })
          if (!res.ok) {
            const text = await res.text()
            throw new Error(text || `状态码 ${res.status}`)
          }
          const data = (await res.json()) as ChatStartResult
          if (!data?.job_id) throw new Error('任务编号缺失')
          const nextPending: PendingChatJob = {
            job_id: data.job_id,
            request_id: requestId,
            placeholder_id: placeholderId,
            user_text: userText,
            session_id: sessionId,
            created_at: Date.now(),
          }
          pendingRecoveredFromStorageRef.current = false
          safeLocalStorageSetItem(pendingKey, JSON.stringify(nextPending))
          setPendingChatJob(nextPending)
          onSendSuccess()
        } catch (err: unknown) {
          updateMessage(placeholderId, { content: `抱歉，请求失败：${toErrorMessage(err)}`, time: nowTime() })
          setSending(false)
          skipAutoSessionLoadIdRef.current = sessionId
          pendingRecoveredFromStorageRef.current = false
          setPendingChatJob(null)
        }
      })

      if (!lockAcquired) {
        await waitPendingSync()
        return
      }

      if (!startedSubmission) {
        await syncPendingFromStorage({ verifyRemote: true })
      }
    },
    [
      verifiedStudent,
      pendingChatJob?.job_id,
      activePersonaId,
      input,
      attachments,
      pendingChatKeyPrefix,
      activeSessionId,
      todayAssignment,
      todayDate,
      onSendSuccess,
      messages,
      apiBase,
      setVerifyError,
      setVerifyOpen,
      setSending,
      setInput,
      setActiveSession,
      setPendingChatJob,
      setMessages,
      updateMessage,
      pendingRecoveredFromStorageRef,
      skipAutoSessionLoadIdRef,
    ],
  )

  return { handleSend }
}
