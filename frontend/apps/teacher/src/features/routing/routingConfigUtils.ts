import type { RoutingConfig } from './routingTypes'

export const cloneConfig = (config: RoutingConfig): RoutingConfig => ({
  schema_version: config.schema_version,
  enabled: Boolean(config.enabled),
  version: Number(config.version || 1),
  updated_at: config.updated_at || '',
  updated_by: config.updated_by || '',
  channels: (config.channels || []).map((channel) => ({
    id: channel.id || '',
    title: channel.title || '',
    target: {
      provider: channel.target?.provider || '',
      mode: channel.target?.mode || '',
      model: channel.target?.model || '',
    },
    params: {
      temperature: channel.params?.temperature ?? null,
      max_tokens: channel.params?.max_tokens ?? null,
    },
    fallback_channels: Array.isArray(channel.fallback_channels) ? [...channel.fallback_channels] : [],
    capabilities: {
      tools: channel.capabilities?.tools ?? true,
      json: channel.capabilities?.json ?? true,
    },
  })),
  rules: (config.rules || []).map((rule) => ({
    id: rule.id || '',
    priority: Number(rule.priority || 0),
    enabled: rule.enabled !== false,
    match: {
      roles: Array.isArray(rule.match?.roles) ? [...rule.match.roles] : [],
      skills: Array.isArray(rule.match?.skills) ? [...rule.match.skills] : [],
      kinds: Array.isArray(rule.match?.kinds) ? [...rule.match.kinds] : [],
      needs_tools: rule.match?.needs_tools ?? undefined,
      needs_json: rule.match?.needs_json ?? undefined,
    },
    route: { channel_id: rule.route?.channel_id || '' },
  })),
})
