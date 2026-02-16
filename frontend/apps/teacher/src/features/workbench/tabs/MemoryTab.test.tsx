import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import MemoryTab, { type MemoryTabProps } from './MemoryTab'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const buildProps = (override?: Partial<MemoryTabProps>): MemoryTabProps => ({
  memoryStatusFilter: 'all',
  setMemoryStatusFilter: () => undefined,
  memoryInsights: null,
  proposalError: '',
  proposalLoading: false,
  proposals: [],
  onDeleteProposal: async () => undefined,
  studentMemoryStatusFilter: 'proposed',
  setStudentMemoryStatusFilter: () => undefined,
  studentMemoryStudentFilter: '',
  setStudentMemoryStudentFilter: () => undefined,
  studentMemoryInsights: null,
  studentProposalError: '',
  studentProposalLoading: false,
  studentProposals: [],
  onReviewStudentProposal: async () => undefined,
  onDeleteStudentProposal: async () => undefined,
  ...override,
})

describe('MemoryTab', () => {
  it('shows delete button and emits teacher proposal id when clicked', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const onDeleteProposal = vi.fn(async () => undefined)

    render(
      <MemoryTab
        {...buildProps({
          proposals: [
            {
              proposal_id: 'p-100',
              status: 'applied',
              title: '偏好',
              content: '以后先给答案再解释。',
              source: 'auto',
            },
          ],
          onDeleteProposal,
        })}
      />,
    )

    fireEvent.click(screen.getAllByRole('button', { name: '删除' })[0])
    expect(onDeleteProposal).toHaveBeenCalledTimes(1)
    expect(onDeleteProposal).toHaveBeenCalledWith('p-100')
  })

  it('reviews student proposal with approve action', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const onReviewStudentProposal = vi.fn(async () => undefined)

    render(
      <MemoryTab
        {...buildProps({
          studentProposals: [
            {
              proposal_id: 'smem_1',
              student_id: 'S001',
              memory_type: 'learning_preference',
              content: '学生偏好先看结论。',
              status: 'proposed',
              evidence_refs: ['session:main#12'],
            },
          ],
          onReviewStudentProposal,
        })}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '通过' }))
    expect(onReviewStudentProposal).toHaveBeenCalledTimes(1)
    expect(onReviewStudentProposal).toHaveBeenCalledWith('smem_1', true)
  })

  it('reviews student proposal with reject action', async () => {
    const onReviewStudentProposal = vi.fn(async () => undefined)

    render(
      <MemoryTab
        {...buildProps({
          studentProposals: [
            {
              proposal_id: 'smem_1',
              student_id: 'S001',
              memory_type: 'learning_preference',
              content: '学生偏好先看结论。',
              status: 'proposed',
            },
          ],
          onReviewStudentProposal,
        })}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '拒绝' }))
    expect(onReviewStudentProposal).toHaveBeenCalledTimes(1)
    expect(onReviewStudentProposal).toHaveBeenCalledWith('smem_1', false)
  })

  it('deletes student proposal when confirmed', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const onDeleteStudentProposal = vi.fn(async () => undefined)

    render(
      <MemoryTab
        {...buildProps({
          studentProposals: [
            {
              proposal_id: 'smem_2',
              student_id: 'S002',
              memory_type: 'long_term_goal',
              content: '学生长期目标是建立稳定的错题复盘节奏。',
              status: 'applied',
            },
          ],
          onDeleteStudentProposal,
        })}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '删除' }))
    expect(onDeleteStudentProposal).toHaveBeenCalledTimes(1)
    expect(onDeleteStudentProposal).toHaveBeenCalledWith('smem_2')
  })

  it('updates student memory filter controls', async () => {
    const setStudentMemoryStatusFilter = vi.fn()
    const setStudentMemoryStudentFilter = vi.fn()

    render(
      <MemoryTab
        {...buildProps({
          studentMemoryStatusFilter: 'proposed',
          setStudentMemoryStatusFilter,
          setStudentMemoryStudentFilter,
        })}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '已通过' }))
    expect(setStudentMemoryStatusFilter).toHaveBeenCalledWith('applied')

    fireEvent.change(screen.getByPlaceholderText('按学生ID过滤（可选）'), {
      target: { value: 'S1001' },
    })
    expect(setStudentMemoryStudentFilter).toHaveBeenCalledWith('S1001')
  })
})
