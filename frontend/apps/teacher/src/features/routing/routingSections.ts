import type { RoutingSection } from './RoutingPage'

export const ROUTING_SECTIONS: RoutingSection[] = [
  'general',
  'providers',
  'channels',
  'rules',
  'simulate',
  'history',
]

export const isRoutingSection = (value: string | null | undefined): value is RoutingSection =>
  Boolean(value && ROUTING_SECTIONS.includes(value as RoutingSection))
