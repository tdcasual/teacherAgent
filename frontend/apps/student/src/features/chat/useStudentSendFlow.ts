import { useCallback, type FormEvent, type MutableRefObject } from 'react'
import { makeId } from '../../../../shared/id'
import { safeLocalStorageGetItem, safeLocalStorageSetItem } from '../../../../shared/storage'
import { nowTime } from '../../../../shared/time'
import type { AssignmentDetail, ChatStartResult, Message, PendingChatJob, VerifiedStudent } from '../../appTypes'
import { stripTransientPendingBubbles } from './pendingOverlay'
import { withStudentSendLock } from './sendLock'

type UseStudentSendFlowParams = {
  apiBase: string
  input: string
  messages: Message[]
  activeSessionId: string
  todayAssignment: AssignmentDetail | null
  verifiedStudent: VerifiedStudent | null
  pendingChatJob: PendingChatJob | null
  pendingChatKeyPrefix: string
  todayDate: () => string

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

export function useStudentSendFlow(params: UseStudentSendFlowParams) {
  const {
    apiBase,
    input,
    messages,
    activeSessionId,
    todayAssignment,
    verifiedStudent,
    pendingChatJob,
    pendingChatKeyPrefix,
    todayDate,
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
      if (!trimmed) return

      const studentId = verifiedStudent.student_id
      const pendingKey = `${pendingChatKeyPrefix}${studentId}`

      const syncPendingFromStorage = () => {
        try {
          const raw = safeLocalStorageGetItem(pendingKey)
          if (!raw) {
            pendingRecoveredFromStorageRef.current = false
            setPendingChatJob(null)
            setSending(false)
            return false
          }
          const parsed = JSON.parse(raw) as PendingChatJob
          pendingRecoveredFromStorageRef.current = false
          setPendingChatJob(parsed)
          setSending(false)
          return true
        } catch {
          pendingRecoveredFromStorageRef.current = false
          setPendingChatJob(null)
          setSending(false)
          return false
        }
      }

      const waitPendingSync = async (timeoutMs = 2500) => {
        if (typeof window === 'undefined') return false
        setSending(true)
        const started = Date.now()
        while (Date.now() - started < timeoutMs) {
          if (syncPendingFromStorage()) return true
          await new Promise((resolve) => window.setTimeout(resolve, 80))
        }
        setSending(false)
        return false
      }

      let startedSubmission = false

      const lockAcquired = await withStudentSendLock(studentId, async () => {
        if (syncPendingFromStorage()) return

        startedSubmission = true
        const sessionId = activeSessionId || todayAssignment?.assignment_id || `general_${todayDate()}`
        if (!activeSessionId) setActiveSession(sessionId)
        const requestId = `schat_${studentId}_${Date.now()}_${Math.random().toString(16).slice(2)}`
        const placeholderId = `asst_${Date.now()}_${Math.random().toString(16).slice(2)}`

        setMessages((prev) => {
          const next = stripTransientPendingBubbles(prev)
          return [
            ...next,
            { id: makeId(), role: 'user', content: trimmed, time: nowTime() },
            { id: placeholderId, role: 'assistant', content: '正在生成…', time: nowTime() },
          ]
        })
        setInput('')

        const contextMessages = [...messages, { id: 'temp', role: 'user' as const, content: trimmed, time: '' }]
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
              assignment_id: inferredAssignmentId,
              assignment_date: todayDate(),
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
            user_text: trimmed,
            session_id: sessionId,
            created_at: Date.now(),
          }
          pendingRecoveredFromStorageRef.current = false
          safeLocalStorageSetItem(pendingKey, JSON.stringify(nextPending))
          setPendingChatJob(nextPending)
        } catch (err: any) {
          updateMessage(placeholderId, { content: `抱歉，请求失败：${err.message || err}`, time: nowTime() })
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
        syncPendingFromStorage()
      }
    },
    [
      verifiedStudent,
      pendingChatJob?.job_id,
      input,
      pendingChatKeyPrefix,
      activeSessionId,
      todayAssignment,
      todayDate,
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
