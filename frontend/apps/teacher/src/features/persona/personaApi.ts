import type { TeacherPersona, TeacherPersonaListResponse } from '../../appTypes'
import { safeLocalStorageGetItem } from '../../utils/storage'
import { normalizeApiBase } from '../../../../shared/apiBase'
import { toUserFacingErrorMessage } from '../../../../shared/errorMessage'

const readTeacherId = () => (safeLocalStorageGetItem('teacherRoutingTeacherId') || '').trim()

const readDetailField = (value: unknown): unknown => {
  if (!value || typeof value !== 'object') return undefined
  return (value as { detail?: unknown }).detail
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
  const bodyText = await res.text()
  let data: unknown = {}
  if (bodyText) {
    try {
      data = JSON.parse(bodyText)
    } catch {
      data = { error: bodyText }
    }
  }
  if (!res.ok) {
    const detail = readDetailField(data)
    const errMsg = toUserFacingErrorMessage(detail ?? data, `请求失败（${res.status}）`)
    throw new Error(errMsg || `状态码 ${res.status}`)
  }
  return data as T
}

export const fetchTeacherPersonas = async (apiBase: string) => {
  const base = normalizeApiBase(apiBase)
  const teacherId = readTeacherId()
  const query = teacherId ? `?teacher_id=${encodeURIComponent(teacherId)}` : ''
  return requestJson<TeacherPersonaListResponse>(`${base}/teacher/personas${query}`)
}

export const createTeacherPersona = async (
  apiBase: string,
  payload: {
    name: string
    summary?: string
    style_rules: string[]
    few_shot_examples: string[]
    visibility_mode?: string
  },
) => {
  const base = normalizeApiBase(apiBase)
  const teacherId = readTeacherId()
  return requestJson<{ ok: boolean; teacher_id: string; persona: TeacherPersona }>(`${base}/teacher/personas`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ...payload,
      ...(teacherId ? { teacher_id: teacherId } : {}),
    }),
  })
}

export const updateTeacherPersona = async (
  apiBase: string,
  personaId: string,
  payload: {
    summary?: string
    visibility_mode?: string
    lifecycle_status?: string
  },
) => {
  const base = normalizeApiBase(apiBase)
  const teacherId = readTeacherId()
  return requestJson<{ ok: boolean; teacher_id: string; persona: TeacherPersona }>(
    `${base}/teacher/personas/${encodeURIComponent(personaId)}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...payload,
        ...(teacherId ? { teacher_id: teacherId } : {}),
      }),
    },
  )
}

export const assignTeacherPersona = async (
  apiBase: string,
  personaId: string,
  payload: {
    student_id: string
    status?: 'active' | 'inactive'
  },
) => {
  const base = normalizeApiBase(apiBase)
  const teacherId = readTeacherId()
  return requestJson<{ ok: boolean; teacher_id: string; persona_id: string; student_id: string; status: string }>(
    `${base}/teacher/personas/${encodeURIComponent(personaId)}/assign`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...payload,
        ...(teacherId ? { teacher_id: teacherId } : {}),
      }),
    },
  )
}

export const setTeacherPersonaVisibility = async (
  apiBase: string,
  personaId: string,
  visibilityMode: 'assigned_only' | 'hidden_all',
) => {
  const base = normalizeApiBase(apiBase)
  const teacherId = readTeacherId()
  return requestJson<{ ok: boolean; teacher_id: string; persona: TeacherPersona }>(
    `${base}/teacher/personas/${encodeURIComponent(personaId)}/visibility`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        visibility_mode: visibilityMode,
        ...(teacherId ? { teacher_id: teacherId } : {}),
      }),
    },
  )
}

export const uploadTeacherPersonaAvatar = async (
  apiBase: string,
  personaId: string,
  file: File,
) => {
  const base = normalizeApiBase(apiBase)
  const teacherId = readTeacherId()
  const form = new FormData()
  form.append('file', file)
  if (teacherId) form.append('teacher_id', teacherId)
  return requestJson<{ ok: boolean; teacher_id: string; persona_id: string; avatar_url: string }>(
    `${base}/teacher/personas/${encodeURIComponent(personaId)}/avatar/upload`,
    {
      method: 'POST',
      body: form,
    },
  )
}
