import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import SkillsTab, { type SkillsTabProps } from './SkillsTab'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const baseProps = (): SkillsTabProps => ({
  apiBase: 'http://localhost:8000',
  filteredSkills: [
    {
      id: 'teacher-assignment-ops',
      title: '作业运营',
      desc: '作业进度、未交/逾期名单与发布归档。',
      instructions: '',
      prompts: ['列出今天未交作业的学生。'],
      examples: ['谁没交'],
      keywords: [],
      source_type: 'system',
    },
  ],
  favorites: [],
  activeSkillId: 'teacher-assignment-ops',
  skillPinned: true,
  skillQuery: '',
  showFavoritesOnly: false,
  skillsLoading: false,
  skillsError: '',
  fetchSkills: async () => undefined,
  chooseSkill: () => undefined,
  toggleFavorite: () => undefined,
  insertPrompt: () => undefined,
  insertInvocationTokenAtCursor: () => undefined,
  stopKeyPropagation: () => undefined,
  setSkillQuery: () => undefined,
  setShowFavoritesOnly: () => undefined,
  setSkillPinned: () => undefined,
  setComposerWarning: () => undefined,
})

describe('SkillsTab copy', () => {
  it('uses workflow-oriented capability wording', () => {
    render(<SkillsTab {...baseProps()} />)

    expect(screen.getByPlaceholderText('搜索教学能力')).toBeTruthy()
    expect(screen.getByRole('button', { name: '切回自动推荐' })).toBeTruthy()
    expect(screen.getByText('当前仅保留系统内置教学能力，可直接选择或让系统自动推荐。')).toBeTruthy()
    expect(screen.getByRole('button', { name: '收藏能力' })).toBeTruthy()
  })
})
