import type {
  RoutingOverview,
  RoutingProposalDetail,
  RoutingProposalResult,
  RoutingRollbackResult,
  RoutingSimulateResult,
} from './routingTypes'

const normalizeBase = (base: string) => (base || '').trim().replace(/\/+$/, '')

const toQuery = (params: Record<string, string | number | undefined>) => {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, val]) => {
    if (val === undefined || val === '') return
    search.set(key, String(val))
  })
  const text = search.toString()
  return text ? `?${text}` : ''
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
    const detail = (data as any)?.detail
    const errMsg = typeof detail === 'string' ? detail : JSON.stringify(detail || data || {})
    throw new Error(errMsg || `状态码 ${res.status}`)
  }
  return data as T
}

export const fetchRoutingOverview = async (
  apiBase: string,
  params?: { teacher_id?: string; history_limit?: number; proposal_limit?: number; proposal_status?: string },
) => {
  const base = normalizeBase(apiBase)
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
  const base = normalizeBase(apiBase)
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
  const base = normalizeBase(apiBase)
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
  const base = normalizeBase(apiBase)
  return requestJson<RoutingProposalResult>(`${base}/teacher/llm-routing/proposals/${encodeURIComponent(proposalId)}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export const fetchRoutingProposalDetail = async (apiBase: string, proposalId: string, teacherId?: string) => {
  const base = normalizeBase(apiBase)
  const query = toQuery({ teacher_id: teacherId || undefined })
  return requestJson<RoutingProposalDetail>(`${base}/teacher/llm-routing/proposals/${encodeURIComponent(proposalId)}${query}`)
}

export const rollbackRoutingConfig = async (
  apiBase: string,
  payload: { teacher_id?: string; target_version: number; note?: string },
) => {
  const base = normalizeBase(apiBase)
  return requestJson<RoutingRollbackResult>(`${base}/teacher/llm-routing/rollback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}
