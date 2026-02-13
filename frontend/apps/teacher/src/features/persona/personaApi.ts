import type { TeacherPersona, TeacherPersonaListResponse } from '../../appTypes'

const normalizeBase = (base: string) => (base || '').trim().replace(/\/+$/, '')

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
    const errMsg = typeof detail === 'string' ? detail : JSON.stringify(detail || data || {})
    throw new Error(errMsg || `状态码 ${res.status}`)
  }
  return data as T
}

export const fetchTeacherPersonas = async (apiBase: string) => {
  const base = normalizeBase(apiBase)
  return requestJson<TeacherPersonaListResponse>(`${base}/teacher/personas`)
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
  const base = normalizeBase(apiBase)
  return requestJson<{ ok: boolean; teacher_id: string; persona: TeacherPersona }>(`${base}/teacher/personas`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
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
  const base = normalizeBase(apiBase)
  return requestJson<{ ok: boolean; teacher_id: string; persona: TeacherPersona }>(
    `${base}/teacher/personas/${encodeURIComponent(personaId)}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
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
  const base = normalizeBase(apiBase)
  return requestJson<{ ok: boolean; teacher_id: string; persona_id: string; student_id: string; status: string }>(
    `${base}/teacher/personas/${encodeURIComponent(personaId)}/assign`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )
}

export const setTeacherPersonaVisibility = async (
  apiBase: string,
  personaId: string,
  visibilityMode: 'assigned_only' | 'hidden_all',
) => {
  const base = normalizeBase(apiBase)
  return requestJson<{ ok: boolean; teacher_id: string; persona: TeacherPersona }>(
    `${base}/teacher/personas/${encodeURIComponent(personaId)}/visibility`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ visibility_mode: visibilityMode }),
    },
  )
}

