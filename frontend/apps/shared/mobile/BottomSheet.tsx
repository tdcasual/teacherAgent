import { useEffect, type ReactNode } from 'react'

type BottomSheetProps = {
  open: boolean
  onClose: () => void
  title?: string
  children: ReactNode
  footer?: ReactNode
  className?: string
}

export function BottomSheet({
  open,
  onClose,
  title = '面板',
  children,
  footer,
  className = '',
}: BottomSheetProps) {
  useEffect(() => {
    if (!open) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="mobile-sheet-layer">
      <button
        type="button"
        className="mobile-sheet-overlay"
        data-testid="mobile-sheet-overlay"
        aria-label="关闭面板"
        onClick={onClose}
      />
      <section
        className={`mobile-sheet-panel ${className}`.trim()}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <header className="mobile-sheet-header">
          <h2 className="mobile-sheet-title">{title}</h2>
          <button type="button" className="mobile-sheet-close" aria-label="关闭" onClick={onClose}>
            关闭
          </button>
        </header>
        <div className="mobile-sheet-body">{children}</div>
        {footer ? <footer className="mobile-sheet-footer">{footer}</footer> : null}
      </section>
    </div>
  )
}
