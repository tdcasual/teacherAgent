import { useCallback, useEffect, useMemo, useState } from 'react'
import { safeLocalStorageGetItem, safeLocalStorageRemoveItem, safeLocalStorageSetItem } from './storage'

export type AttachmentRef = {
  attachment_id: string
}

export type ComposerAttachment = {
  localId: string
  attachmentId: string
  fileName: string
  sizeBytes: number
  status: 'uploading' | 'ready' | 'failed'
  error: string
}

type UploadAttachmentItem = {
  attachment_id?: string
  file_name?: string
  size_bytes?: number
  status?: string
  error_code?: string
  error_detail?: string
}

type UploadAttachmentResponse = {
  attachments?: UploadAttachmentItem[]
}

type AttachmentStatusResponse = {
  attachments?: UploadAttachmentItem[]
}

type PersistedReadyAttachment = {
  attachmentId: string
  fileName: string
  sizeBytes: number
}

type UseChatAttachmentsParams = {
  apiBase: string
  role: 'teacher' | 'student'
  sessionId: string
  teacherId?: string
  studentId?: string
  persistenceKey?: string
}

const MAX_FILES_PER_MESSAGE = 5
const MAX_TOTAL_SIZE_BYTES = 30 * 1024 * 1024
const READY_ATTACHMENTS_STORAGE_PREFIX = 'chatReadyAttachments:'

const toErrorMessage = (error: unknown, fallback = '上传失败') => {
  if (error instanceof Error) {
    const msg = error.message.trim()
    if (msg) return msg
  }
  const raw = String(error || '').trim()
  return raw || fallback
}

const makeLocalId = () => `attach_${Date.now()}_${Math.random().toString(16).slice(2)}`

export function useChatAttachments(params: UseChatAttachmentsParams) {
  const { apiBase, role, sessionId, teacherId = '', studentId = '', persistenceKey = '' } = params
  const [attachments, setAttachments] = useState<ComposerAttachment[]>([])
  const persistenceStorageKey = persistenceKey
    ? `${READY_ATTACHMENTS_STORAGE_PREFIX}${persistenceKey}`
    : ''

  useEffect(() => {
    let cancelled = false

    const restoreReadyAttachments = async () => {
      if (!persistenceStorageKey) return
      setAttachments([])

      const raw = safeLocalStorageGetItem(persistenceStorageKey)
      if (!raw) return

      let parsed: PersistedReadyAttachment[] = []
      try {
        const payload = JSON.parse(raw) as unknown
        if (Array.isArray(payload)) {
          parsed = payload
            .map((item) => {
              if (!item || typeof item !== 'object') return null
              const data = item as Record<string, unknown>
              const attachmentId = String(data.attachmentId || '').trim()
              if (!attachmentId) return null
              return {
                attachmentId,
                fileName: String(data.fileName || '').trim(),
                sizeBytes: Number(data.sizeBytes || 0),
              }
            })
            .filter((item): item is PersistedReadyAttachment => Boolean(item))
        }
      } catch {
        parsed = []
      }

      if (!parsed.length) {
        safeLocalStorageRemoveItem(persistenceStorageKey)
        return
      }

      const attachmentIds = Array.from(new Set(parsed.map((item) => item.attachmentId).filter(Boolean)))
      if (!attachmentIds.length) {
        safeLocalStorageRemoveItem(persistenceStorageKey)
        return
      }

      try {
        const query = new URLSearchParams()
        query.set('role', role)
        query.set('session_id', sessionId || 'main')
        if (role === 'teacher') query.set('teacher_id', teacherId)
        if (role === 'student') query.set('student_id', studentId)
        for (const attachmentId of attachmentIds) query.append('attachment_ids', attachmentId)

        const res = await fetch(`${apiBase}/chat/attachments/status?${query.toString()}`)
        if (!res.ok) throw new Error(`状态码 ${res.status}`)
        const payload = (await res.json()) as AttachmentStatusResponse
        const statusItems = Array.isArray(payload.attachments) ? payload.attachments : []
        const statusMap = new Map<string, UploadAttachmentItem>()
        for (const item of statusItems) {
          const attachmentId = String(item.attachment_id || '').trim()
          if (!attachmentId) continue
          statusMap.set(attachmentId, item)
        }

        const restored: ComposerAttachment[] = []
        for (const item of parsed) {
          const statusItem = statusMap.get(item.attachmentId)
          if (!statusItem) continue
          if (String(statusItem.status || '') !== 'ready') continue
          restored.push({
            localId: makeLocalId(),
            attachmentId: item.attachmentId,
            fileName: String(statusItem.file_name || item.fileName || item.attachmentId),
            sizeBytes: Number(statusItem.size_bytes || item.sizeBytes || 0),
            status: 'ready',
            error: '',
          })
        }

        if (cancelled) return
        setAttachments(restored)
        if (!restored.length) safeLocalStorageRemoveItem(persistenceStorageKey)
      } catch {
        if (cancelled) return
        setAttachments([])
        safeLocalStorageRemoveItem(persistenceStorageKey)
      }
    }

    void restoreReadyAttachments()
    return () => {
      cancelled = true
    }
  }, [apiBase, persistenceStorageKey, role, sessionId, studentId, teacherId])

  useEffect(() => {
    if (!persistenceStorageKey) return
    const ready = attachments
      .filter((item) => item.status === 'ready' && item.attachmentId)
      .map((item) => ({
        attachmentId: item.attachmentId,
        fileName: item.fileName,
        sizeBytes: Number(item.sizeBytes || 0),
      }))
    if (!ready.length) {
      safeLocalStorageRemoveItem(persistenceStorageKey)
      return
    }
    safeLocalStorageSetItem(persistenceStorageKey, JSON.stringify(ready))
  }, [attachments, persistenceStorageKey])

  const addFiles = useCallback(
    async (files: File[]) => {
      const selected = files.filter(Boolean)
      if (!selected.length) return
      const currentCount = attachments.length
      if (currentCount + selected.length > MAX_FILES_PER_MESSAGE) {
        const reason = `单条消息最多上传 ${MAX_FILES_PER_MESSAGE} 个文件`
        setAttachments((prev) => [
          ...prev,
          ...selected.map((file) => ({
            localId: makeLocalId(),
            attachmentId: '',
            fileName: file.name,
            sizeBytes: file.size,
            status: 'failed' as const,
            error: reason,
          })),
        ])
        return
      }
      const currentSize = attachments.reduce((sum, item) => sum + Number(item.sizeBytes || 0), 0)
      const selectedSize = selected.reduce((sum, file) => sum + Number(file.size || 0), 0)
      if (currentSize + selectedSize > MAX_TOTAL_SIZE_BYTES) {
        const reason = '单条消息文件总大小不能超过 30MB'
        setAttachments((prev) => [
          ...prev,
          ...selected.map((file) => ({
            localId: makeLocalId(),
            attachmentId: '',
            fileName: file.name,
            sizeBytes: file.size,
            status: 'failed' as const,
            error: reason,
          })),
        ])
        return
      }

      const localItems: ComposerAttachment[] = selected.map((file) => ({
        localId: makeLocalId(),
        attachmentId: '',
        fileName: file.name,
        sizeBytes: file.size,
        status: 'uploading',
        error: '',
      }))
      setAttachments((prev) => [...prev, ...localItems])

      try {
        const formData = new FormData()
        formData.set('role', role)
        formData.set('session_id', sessionId || 'main')
        formData.set('request_id', `attach_req_${Date.now()}`)
        if (role === 'teacher') formData.set('teacher_id', teacherId)
        if (role === 'student') formData.set('student_id', studentId)
        for (const file of selected) formData.append('files', file)

        const res = await fetch(`${apiBase}/chat/attachments`, {
          method: 'POST',
          body: formData,
        })
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || `状态码 ${res.status}`)
        }
        const payload = (await res.json()) as UploadAttachmentResponse
        const uploaded = Array.isArray(payload.attachments) ? payload.attachments : []

        setAttachments((prev) => {
          const next = [...prev]
          localItems.forEach((local, index) => {
            const target = uploaded[index]
            const pos = next.findIndex((item) => item.localId === local.localId)
            if (pos < 0) return
            if (!target) {
              next[pos] = { ...next[pos], status: 'failed', error: '上传结果缺失' }
              return
            }
            const statusRaw = String(target.status || '')
            const status = statusRaw === 'ready' ? 'ready' : 'failed'
            next[pos] = {
              ...next[pos],
              attachmentId: String(target.attachment_id || ''),
              fileName: String(target.file_name || next[pos].fileName),
              sizeBytes: Number(target.size_bytes || next[pos].sizeBytes || 0),
              status,
              error: status === 'failed'
                ? String(target.error_detail || target.error_code || '解析失败')
                : '',
            }
          })
          return next
        })
      } catch (err: unknown) {
        const message = toErrorMessage(err)
        setAttachments((prev) =>
          prev.map((item) =>
            localItems.some((local) => local.localId === item.localId)
              ? { ...item, status: 'failed', error: message }
              : item,
          ),
        )
      }
    },
    [apiBase, attachments, role, sessionId, studentId, teacherId],
  )

  const removeAttachment = useCallback(
    async (localId: string) => {
      const target = attachments.find((item) => item.localId === localId)
      setAttachments((prev) => prev.filter((item) => item.localId !== localId))
      if (!target?.attachmentId) return

      const params = new URLSearchParams()
      params.set('role', role)
      params.set('session_id', sessionId || 'main')
      if (role === 'teacher') params.set('teacher_id', teacherId)
      if (role === 'student') params.set('student_id', studentId)
      try {
        await fetch(`${apiBase}/chat/attachments/${encodeURIComponent(target.attachmentId)}?${params.toString()}`, {
          method: 'DELETE',
        })
      } catch {
        // Ignore delete failures; local removal is enough to unblock UX.
      }
    },
    [apiBase, attachments, role, sessionId, studentId, teacherId],
  )

  const clearReadyAttachments = useCallback(() => {
    setAttachments((prev) => prev.filter((item) => item.status !== 'ready'))
  }, [])

  const readyAttachmentRefs = useMemo<AttachmentRef[]>(
    () =>
      attachments
        .filter((item) => item.status === 'ready' && item.attachmentId)
        .map((item) => ({ attachment_id: item.attachmentId })),
    [attachments],
  )

  const hasSendableAttachments = readyAttachmentRefs.length > 0
  const uploading = attachments.some((item) => item.status === 'uploading')

  return {
    attachments,
    addFiles,
    removeAttachment,
    clearReadyAttachments,
    readyAttachmentRefs,
    hasSendableAttachments,
    uploading,
  }
}
