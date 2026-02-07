import type { ParsedInvocation } from './invocation'

type DecideSkillRoutingInput = {
  parsedInvocation: ParsedInvocation
  activeSkillId: string
  skillPinned: boolean
}

export type SkillRoutingDecision = {
  explicitSkillRequested: boolean
  explicitSkillResolved: boolean
  shouldPinEffectiveSkill: boolean
  skillIdForRequest?: string
  normalizedWarnings: string[]
}

export const decideSkillRouting = ({
  parsedInvocation,
  activeSkillId,
  skillPinned,
}: DecideSkillRoutingInput): SkillRoutingDecision => {
  const explicitSkillRequested = Boolean(parsedInvocation.requestedSkillId)
  const explicitSkillResolved =
    explicitSkillRequested && parsedInvocation.effectiveSkillId === parsedInvocation.requestedSkillId
  const shouldPinEffectiveSkill = explicitSkillResolved && Boolean(parsedInvocation.effectiveSkillId)
  const normalizedWarnings = parsedInvocation.warnings.map((warning) => {
    if (!skillPinned && explicitSkillRequested && !explicitSkillResolved && warning.startsWith('未识别的技能：$')) {
      return `未识别的技能：$${parsedInvocation.requestedSkillId}，已使用自动路由`
    }
    return warning
  })
  const skillIdForRequest =
    explicitSkillResolved && parsedInvocation.effectiveSkillId
      ? parsedInvocation.effectiveSkillId
      : skillPinned && activeSkillId
        ? activeSkillId
        : undefined

  return {
    explicitSkillRequested,
    explicitSkillResolved,
    shouldPinEffectiveSkill,
    skillIdForRequest,
    normalizedWarnings,
  }
}
