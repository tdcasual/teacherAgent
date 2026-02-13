import type {
  RoutingOverview,
  TeacherProviderProbeModelsResult,
  TeacherProviderRegistryMutationResult,
  TeacherProviderRegistryOverview,
  RoutingProposalDetail,
  RoutingProposalResult,
  RoutingRollbackResult,
  RoutingSimulateResult,
} from './routingTypes'
import { normalizeApiBase } from '../../../../shared/apiBase'
import { toUserFacingErrorMessage } from '../../../../shared/errorMessage'

const toQuery = (params: Record<string, string | number | undefined>) => {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, val]) => {
    if (val === undefined || val === '') return
    search.set(key, String(val))
  })
  const text = search.toString()
  return text ? `?${text}` : ''
}

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

export const fetchRoutingOverview = async (
  apiBase: string,
  params?: { teacher_id?: string; history_limit?: number; proposal_limit?: number; proposal_status?: string },
) => {
  const base = normalizeApiBase(apiBase)
  const query = toQuery({
    teacher_id: params?.teacher_id,
    history_limit: params?.history_limit,
    proposal_limit: params?.proposal_limit,
    proposal_status: params?.proposal_status,
  })
  return requestJson<RoutingOverview>(`${base}/teacher/llm-routing${query}`)
}

export const simulateRouting = async (
  apiBase: string,
  payload: {
    teacher_id?: string
    role?: string
    skill_id?: string
    kind?: string
    needs_tools?: boolean
    needs_json?: boolean
    config?: Record<string, unknown>
  },
) => {
  const base = normalizeApiBase(apiBase)
  return requestJson<RoutingSimulateResult>(`${base}/teacher/llm-routing/simulate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export const createRoutingProposal = async (
  apiBase: string,
  payload: { teacher_id?: string; note?: string; config: Record<string, unknown> },
) => {
  const base = normalizeApiBase(apiBase)
  return requestJson<RoutingProposalResult>(`${base}/teacher/llm-routing/proposals`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export const reviewRoutingProposal = async (
  apiBase: string,
  proposalId: string,
  payload: { teacher_id?: string; approve: boolean },
) => {
  const base = normalizeApiBase(apiBase)
  return requestJson<RoutingProposalResult>(`${base}/teacher/llm-routing/proposals/${encodeURIComponent(proposalId)}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export const fetchRoutingProposalDetail = async (apiBase: string, proposalId: string, teacherId?: string) => {
  const base = normalizeApiBase(apiBase)
  const query = toQuery({ teacher_id: teacherId || undefined })
  return requestJson<RoutingProposalDetail>(`${base}/teacher/llm-routing/proposals/${encodeURIComponent(proposalId)}${query}`)
}

export const rollbackRoutingConfig = async (
  apiBase: string,
  payload: { teacher_id?: string; target_version: number; note?: string },
) => {
  const base = normalizeApiBase(apiBase)
  return requestJson<RoutingRollbackResult>(`${base}/teacher/llm-routing/rollback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export const fetchProviderRegistry = async (apiBase: string, params?: { teacher_id?: string }) => {
  const base = normalizeApiBase(apiBase)
  const query = toQuery({ teacher_id: params?.teacher_id })
  return requestJson<TeacherProviderRegistryOverview>(`${base}/teacher/provider-registry${query}`)
}

export const createProviderRegistryItem = async (
  apiBase: string,
  payload: {
    teacher_id?: string
    provider_id?: string
    display_name?: string
    base_url: string
    api_key: string
    default_model?: string
    enabled?: boolean
  },
) => {
  const base = normalizeApiBase(apiBase)
  return requestJson<TeacherProviderRegistryMutationResult>(`${base}/teacher/provider-registry/providers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export const updateProviderRegistryItem = async (
  apiBase: string,
  providerId: string,
  payload: {
    teacher_id?: string
    display_name?: string
    base_url?: string
    api_key?: string
    default_model?: string
    enabled?: boolean
  },
) => {
  const base = normalizeApiBase(apiBase)
  return requestJson<TeacherProviderRegistryMutationResult>(
    `${base}/teacher/provider-registry/providers/${encodeURIComponent(providerId)}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )
}

export const deleteProviderRegistryItem = async (
  apiBase: string,
  providerId: string,
  payload: { teacher_id?: string },
) => {
  const base = normalizeApiBase(apiBase)
  return requestJson<TeacherProviderRegistryMutationResult>(
    `${base}/teacher/provider-registry/providers/${encodeURIComponent(providerId)}`,
    {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )
}

export const probeProviderRegistryModels = async (
  apiBase: string,
  providerId: string,
  payload: { teacher_id?: string },
) => {
  const base = normalizeApiBase(apiBase)
  return requestJson<TeacherProviderProbeModelsResult>(
    `${base}/teacher/provider-registry/providers/${encodeURIComponent(providerId)}/probe-models`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )
}
