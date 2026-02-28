import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MobileTabBar } from './MobileTabBar'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('MobileTabBar', () => {
  it('marks the active tab with aria-current', () => {
    render(
      <MobileTabBar
        items={[
          { id: 'chat', label: '聊天' },
          { id: 'sessions', label: '会话' },
        ]}
        activeId="sessions"
        onChange={() => {}}
      />,
    )

    expect(screen.getByRole('button', { name: '会话' }).getAttribute('aria-current')).toBe('page')
    expect(screen.getByRole('button', { name: '聊天' }).getAttribute('aria-current')).toBeNull()
  })

  it('calls onChange when clicking a tab', () => {
    const onChange = vi.fn()
    render(
      <MobileTabBar
        items={[
          { id: 'chat', label: '聊天' },
          { id: 'sessions', label: '会话' },
          { id: 'learning', label: '学习' },
        ]}
        activeId="chat"
        onChange={onChange}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '学习' }))
    expect(onChange).toHaveBeenCalledTimes(1)
    expect(onChange).toHaveBeenCalledWith('learning')
  })
})
