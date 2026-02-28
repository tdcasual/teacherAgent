import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { BottomSheet } from './BottomSheet'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('BottomSheet', () => {
  it('renders children when open', () => {
    render(
      <BottomSheet open onClose={() => {}} title="Sheet">
        content
      </BottomSheet>,
    )
    expect(screen.getByRole('dialog', { name: 'Sheet' })).toBeTruthy()
    expect(screen.getByText('content')).toBeTruthy()
  })

  it('calls onClose when clicking overlay', () => {
    const onClose = vi.fn()
    const view = render(
      <BottomSheet open onClose={onClose} title="Sheet">
        content
      </BottomSheet>,
    )
    fireEvent.click(view.getByTestId('mobile-sheet-overlay'))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('calls onClose when pressing escape', () => {
    const onClose = vi.fn()
    render(
      <BottomSheet open onClose={onClose} title="Sheet">
        content
      </BottomSheet>,
    )
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('locks body scroll while open and restores on close', () => {
    document.body.style.overflow = 'auto'
    const onClose = vi.fn()
    const view = render(
      <BottomSheet open onClose={onClose} title="Sheet">
        content
      </BottomSheet>,
    )
    expect(document.body.style.overflow).toBe('hidden')
    view.rerender(
      <BottomSheet open={false} onClose={onClose} title="Sheet">
        content
      </BottomSheet>,
    )
    expect(document.body.style.overflow).toBe('auto')
  })

  it('restores focus to previously focused element when closing', async () => {
    const opener = document.createElement('button')
    opener.textContent = 'open-sheet'
    document.body.appendChild(opener)
    opener.focus()

    const onClose = vi.fn()
    const view = render(
      <BottomSheet open onClose={onClose} title="Sheet">
        <button type="button">inside</button>
      </BottomSheet>,
    )

    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(document.activeElement).toBe(screen.getByRole('button', { name: '关闭' }))

    view.rerender(
      <BottomSheet open={false} onClose={onClose} title="Sheet">
        <button type="button">inside</button>
      </BottomSheet>,
    )
    expect(document.activeElement).toBe(opener)
    opener.remove()
  })

  it('traps tab focus inside panel', async () => {
    render(
      <BottomSheet open onClose={() => {}} title="Sheet">
        <button type="button">inside</button>
      </BottomSheet>,
    )
    const closeButton = screen.getByRole('button', { name: '关闭' })
    const insideButton = screen.getByRole('button', { name: 'inside' })

    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(document.activeElement).toBe(closeButton)
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true })
    expect(document.activeElement).toBe(insideButton)
    fireEvent.keyDown(document, { key: 'Tab' })
    expect(document.activeElement).toBe(closeButton)
  })
})
