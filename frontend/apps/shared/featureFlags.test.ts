import { describe, expect, it } from 'vitest'
import { readFeatureFlag } from './featureFlags'

describe('readFeatureFlag', () => {
  it('returns fallback false when flag is missing', () => {
    expect(readFeatureFlag('mobileShellV2', false, {})).toBe(false)
  })

  it('returns fallback true when flag is missing', () => {
    expect(readFeatureFlag('mobileShellV2', true, {})).toBe(true)
  })

  it('parses true-like values', () => {
    expect(readFeatureFlag('mobileShellV2', false, { mobileShellV2: '1' })).toBe(true)
    expect(readFeatureFlag('mobileShellV2', false, { mobileShellV2: 'true' })).toBe(true)
    expect(readFeatureFlag('mobileShellV2', false, { mobileShellV2: 'TRUE' })).toBe(true)
  })

  it('parses non-true values as false', () => {
    expect(readFeatureFlag('mobileShellV2', true, { mobileShellV2: '0' })).toBe(false)
    expect(readFeatureFlag('mobileShellV2', true, { mobileShellV2: 'false' })).toBe(false)
    expect(readFeatureFlag('mobileShellV2', true, { mobileShellV2: 'anything-else' })).toBe(false)
  })
})
