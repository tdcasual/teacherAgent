import assert from 'node:assert/strict'
import { parseInvocationInput } from './invocation.ts'

const knownSkills = ['physics-teacher-ops', 'physics-homework-generator']

const parsed = parseInvocationInput('$physics-teacher-ops 生成作业', {
  knownSkillIds: knownSkills,
  activeSkillId: 'physics-teacher-ops',
})

assert.equal(parsed.effectiveSkillId, 'physics-teacher-ops')
assert.equal(parsed.cleanedInput, '生成作业')
assert.equal(parsed.warnings.length, 0)

const unknown = parseInvocationInput('$unknown 讲解静电场', {
  knownSkillIds: knownSkills,
  activeSkillId: 'physics-teacher-ops',
})

assert.equal(unknown.effectiveSkillId, 'physics-teacher-ops')
assert.ok(unknown.warnings.length >= 1)

console.log('invocation selftest passed')
