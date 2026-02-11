import { useEffect, useRef, type ReactNode } from 'react'

type SettingsSection = {
  id: string
  label: string
}

type Props = {
  open: boolean
  onClose: () => void
  sections: SettingsSection[]
  activeSection: string
  onSectionChange: (id: string) => void
  title?: string
  statusBar?: ReactNode
  children: ReactNode
}

export default function SettingsModal({
  open,
  onClose,
  sections,
  activeSection,
  onSectionChange,
  title = '设置',
  statusBar,
  children,
}: Props) {
  const mouseDownOnOverlay = useRef(false)

  useEffect(() => {
    if (!open) return
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  if (!open) return null
  return (
    <div
      className="settings-overlay fixed inset-0 z-100 bg-black/50 backdrop-blur-sm flex items-center justify-center"
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onMouseDown={(e) => { mouseDownOnOverlay.current = e.target === e.currentTarget }}
      onClick={(e) => { if (e.target === e.currentTarget && mouseDownOnOverlay.current) onClose() }}
    >
      <div
        className="settings-dialog bg-surface rounded-[12px] shadow-[0_16px_48px_rgba(0,0,0,0.16)] flex flex-col overflow-hidden max-[640px]:w-screen max-[640px]:max-h-screen max-[640px]:rounded-none"
        style={{ width: 'min(860px, 92vw)', maxHeight: 'min(640px, 85vh)' }}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-border shrink-0">
          <h2 className="m-0 text-base font-semibold">{title}</h2>
          <button
            className="bg-transparent border-none text-lg cursor-pointer text-muted px-2 py-1 rounded-[6px] transition-colors duration-150 hover:bg-surface-soft hover:text-ink"
            onClick={onClose}
            aria-label="关闭"
          >
            ✕
          </button>
        </div>
        {statusBar}
        <div className="flex flex-1 min-h-0 overflow-hidden max-[640px]:flex-col">
          <nav className="settings-nav w-40 shrink-0 border-r border-border py-3 px-2 flex flex-col gap-0.5 overflow-y-auto max-[640px]:w-full max-[640px]:flex-row max-[640px]:border-r-0 max-[640px]:border-b max-[640px]:border-border max-[640px]:overflow-x-auto max-[640px]:p-2 max-[640px]:gap-1">
            {sections.map((s) => (
              <button
                key={s.id}
                className={`bg-transparent border-none text-left px-3 py-2 rounded-lg text-[13px] text-muted cursor-pointer transition-colors duration-150 hover:bg-surface-soft hover:text-ink max-[640px]:whitespace-nowrap max-[640px]:shrink-0 ${
                  activeSection === s.id
                    ? 'active bg-accent-soft text-accent font-semibold hover:bg-accent-soft hover:text-accent'
                    : ''
                }`}
                onClick={() => onSectionChange(s.id)}
              >
                {s.label}
              </button>
            ))}
          </nav>
          <div className="flex-1 px-5 py-4 overflow-y-auto min-h-0">{children}</div>
        </div>
      </div>
    </div>
  )
}
