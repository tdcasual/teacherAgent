import assert from 'node:assert/strict'
import { decideSkillRouting } from './requestRouting.ts'

const explicitSkill = decideSkillRouting({
  parsedInvocation: {
    cleanedInput: '生成作业',
    requestedAgentId: '',
    requestedSkillId: 'physics-homework-generator',
    effectiveAgentId: 'default',
    effectiveSkillId: 'physics-homework-generator',
    warnings: [],
    tokens: [],
  },
  activeSkillId: 'physics-teacher-ops',
  skillPinned: false,
})

assert.equal(explicitSkill.skillIdForRequest, 'physics-homework-generator')
assert.equal(explicitSkill.shouldPinEffectiveSkill, true)
assert.equal(explicitSkill.normalizedWarnings.length, 0)

const autoRoute = decideSkillRouting({
  parsedInvocation: {
    cleanedInput: '出一套静电场训练题',
    requestedAgentId: '',
    requestedSkillId: '',
    effectiveAgentId: 'default',
    effectiveSkillId: 'physics-teacher-ops',
    warnings: [],
    tokens: [],
  },
  activeSkillId: 'physics-teacher-ops',
  skillPinned: false,
})

assert.equal(autoRoute.skillIdForRequest, undefined)
assert.equal(autoRoute.shouldPinEffectiveSkill, false)

const unknownSkillInAuto = decideSkillRouting({
  parsedInvocation: {
    cleanedInput: '讲解受力分析',
    requestedAgentId: '',
    requestedSkillId: 'ghost-skill',
    effectiveAgentId: 'default',
    effectiveSkillId: 'physics-teacher-ops',
    warnings: ['未识别的技能：$ghost-skill，已使用 physics-teacher-ops'],
    tokens: [],
  },
  activeSkillId: 'physics-teacher-ops',
  skillPinned: false,
})

assert.equal(unknownSkillInAuto.skillIdForRequest, undefined)
assert.equal(unknownSkillInAuto.normalizedWarnings[0], '未识别的技能：$ghost-skill，已使用自动路由')

console.log('request routing selftest passed')
