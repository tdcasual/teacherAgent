import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import ChatMessages from './ChatMessages'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

type ChatMessagesProps = Parameters<typeof ChatMessages>[0]

const baseProps = (): ChatMessagesProps => ({
  renderedMessages: [
    {
      id: 'm1',
      role: 'assistant',
      html: '<p>hello</p>',
      time: '10:00',
    },
  ],
  sending: false,
  hasPendingChatJob: false,
  typingTimeLabel: '10:01',
  messagesRef: { current: null },
  onMessagesScroll: () => undefined,
  showScrollToBottom: false,
  onScrollToBottom: () => undefined,
  pendingStreamStage: '',
  pendingToolRuns: [],
})

describe('ChatMessages process panel', () => {
  it('renders assistant replies as result blocks and user messages as commands', () => {
    render(
      <ChatMessages
        {...baseProps()}
        renderedMessages={[
          { id: 'm1', role: 'user', html: '<p>生成一份作业</p>', time: '10:00' },
          { id: 'm2', role: 'assistant', html: '<p>已生成作业草稿</p>', time: '10:01' },
        ]}
      />,
    )

    expect(screen.getByText('我的指令 · 10:00')).toBeTruthy()
    expect(screen.getByText('执行结果 · 10:01')).toBeTruthy()
    expect(screen.getByText('已生成作业草稿')).toBeTruthy()
  })

  it('shows process stage and tool status details', () => {
    render(
      <ChatMessages
        {...baseProps()}
        hasPendingChatJob
        pendingStreamStage="处理中"
        pendingToolRuns={[
          { key: 't1', name: 'exam.get', status: 'running' },
          { key: 't2', name: 'exam.analysis.get', status: 'ok', durationMs: 120 },
          { key: 't3', name: 'exam.students.list', status: 'failed', error: 'timeout' },
        ]}
      />,
    )

    expect(screen.getByText('执行过程 · 处理中')).toBeTruthy()
    expect(screen.getByText('进行中 1 · 成功 1 · 失败 1')).toBeTruthy()
    expect(screen.getByText('exam.get')).toBeTruthy()
    expect(screen.getAllByText(/进行中/).length).toBeGreaterThan(0)
    expect(screen.getByText('成功（120ms）')).toBeTruthy()
    expect(screen.getByText('失败：timeout')).toBeTruthy()
  })

  it('supports collapse and expand for process details', () => {
    render(
      <ChatMessages
        {...baseProps()}
        hasPendingChatJob
        pendingStreamStage="处理中"
        pendingToolRuns={[
          { key: 't1', name: 'exam.get', status: 'running' },
        ]}
      />,
    )

    expect(screen.getByText('exam.get')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '收起' }))
    expect(screen.queryByText('exam.get')).toBeNull()
    expect(screen.getByRole('button', { name: '展开' })).toBeTruthy()
  })

  it('filters to failed tools only when requested', () => {
    render(
      <ChatMessages
        {...baseProps()}
        hasPendingChatJob
        pendingStreamStage="处理中"
        pendingToolRuns={[
          { key: 't1', name: 'exam.get', status: 'running' },
          { key: 't2', name: 'exam.analysis.get', status: 'failed', error: '403' },
        ]}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '仅失败' }))
    expect(screen.queryByText('exam.get')).toBeNull()
    expect(screen.getByText('exam.analysis.get')).toBeTruthy()
    expect(screen.getByRole('button', { name: '显示全部' })).toBeTruthy()
  })
})
