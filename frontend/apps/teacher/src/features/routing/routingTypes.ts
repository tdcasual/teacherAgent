export type RoutingCapability = {
  tools: boolean
  json: boolean
}

export type RoutingTarget = {
  provider: string
  mode: string
  model: string
}

export type RoutingParams = {
  temperature: number | null
  max_tokens: number | null
}

export type RoutingChannel = {
  id: string
  title: string
  target: RoutingTarget
  params: RoutingParams
  fallback_channels: string[]
  capabilities: RoutingCapability
}

export type RoutingRuleMatch = {
  roles: string[]
  skills: string[]
  kinds: string[]
  needs_tools?: boolean | null
  needs_json?: boolean | null
}

export type RoutingRule = {
  id: string
  priority: number
  enabled: boolean
  match: RoutingRuleMatch
  route: { channel_id: string }
}

export type RoutingConfig = {
  schema_version: number
  enabled: boolean
  version: number
  updated_at: string
  updated_by: string
  channels: RoutingChannel[]
  rules: RoutingRule[]
}

export type RoutingHistoryItem = {
  file: string
  version: number
  saved_at: string
  saved_by: string
  source: string
  note: string
}

export type RoutingProposalItem = {
  proposal_id: string
  created_at: string
  created_by: string
  status: string
  note: string
  validation_ok: boolean
  proposal_path: string
}

export type RoutingProposalDetail = {
  ok: boolean
  teacher_id: string
  config_path: string
  proposal: {
    proposal_id: string
    created_at?: string
    created_by?: string
    reviewed_at?: string
    reviewed_by?: string
    status?: string
    note?: string
    candidate?: Record<string, unknown>
    validation?: {
      ok?: boolean
      errors?: string[]
      warnings?: string[]
    }
    apply_error?: unknown
    [key: string]: unknown
  }
}

export type RoutingCatalogMode = {
  mode: string
  default_model: string
  model_env: string
}

export type RoutingCatalogProvider = {
  provider: string
  source?: string
  modes: RoutingCatalogMode[]
}

export type RoutingCatalog = {
  providers: RoutingCatalogProvider[]
  defaults: { provider: string; mode: string }
  fallback_chain: string[]
}

export type RoutingOverview = {
  ok: boolean
  teacher_id: string
  routing: RoutingConfig
  validation: { errors: string[]; warnings: string[] }
  history: RoutingHistoryItem[]
  proposals: RoutingProposalItem[]
  catalog?: RoutingCatalog
  config_path: string
}

export type RoutingSimulateDecisionCandidate = {
  channel_id: string
  provider: string
  mode: string
  model: string
  temperature: number | null
  max_tokens: number | null
  capabilities: RoutingCapability
}

export type RoutingSimulateDecision = {
  enabled: boolean
  matched_rule_id: string | null
  reason: string
  selected: boolean
  candidates: RoutingSimulateDecisionCandidate[]
}

export type RoutingSimulateResult = {
  ok: boolean
  teacher_id: string
  context: {
    role?: string | null
    skill_id?: string | null
    kind?: string | null
    needs_tools: boolean
    needs_json: boolean
  }
  decision: RoutingSimulateDecision
  validation: { errors: string[]; warnings: string[] }
  config_override?: boolean
  override_validation?: { ok: boolean; errors: string[]; warnings: string[] }
}

export type RoutingProposalResult = {
  ok: boolean
  proposal_id: string
  status: string
  validation?: { ok: boolean; errors: string[]; warnings: string[] }
  version?: number
  error?: unknown
}

export type RoutingRollbackResult = {
  ok: boolean
  version?: number
  error?: string
}

export type TeacherProviderItem = {
  id: string
  provider: string
  display_name: string
  base_url: string
  api_key_masked: string
  default_mode: string
  default_model: string
  enabled: boolean
  created_at?: string
  updated_at?: string
  source: 'private'
}

export type TeacherProviderRegistryOverview = {
  ok: boolean
  teacher_id: string
  providers: TeacherProviderItem[]
  shared_catalog: RoutingCatalog
  catalog: RoutingCatalog
  config_path: string
}

export type TeacherProviderRegistryMutationResult = {
  ok: boolean
  teacher_id?: string
  provider?: TeacherProviderItem
  provider_id?: string
  error?: string
}

export type TeacherProviderProbeModelsResult = {
  ok: boolean
  teacher_id?: string
  provider_id?: string
  models?: string[]
  error?: string
  detail?: string
}

export const emptyRoutingConfig = (): RoutingConfig => ({
  schema_version: 1,
  enabled: false,
  version: 1,
  updated_at: '',
  updated_by: '',
  channels: [],
  rules: [],
})
