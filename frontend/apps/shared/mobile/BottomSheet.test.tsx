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
})
