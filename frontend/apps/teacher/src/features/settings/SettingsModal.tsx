import { type ReactNode } from 'react'

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
  if (!open) return null
  return (
    <div className="settings-overlay" onClick={onClose}>
      <div className="settings-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="settings-dialog-header">
          <h2>{title}</h2>
          <button className="settings-close-btn" onClick={onClose} aria-label="关闭">
            ✕
          </button>
        </div>
        {statusBar}
        <div className="settings-dialog-body">
          <nav className="settings-nav">
            {sections.map((s) => (
              <button
                key={s.id}
                className={activeSection === s.id ? 'active' : ''}
                onClick={() => onSectionChange(s.id)}
              >
                {s.label}
              </button>
            ))}
          </nav>
          <div className="settings-panel">{children}</div>
        </div>
      </div>
    </div>
  )
}
