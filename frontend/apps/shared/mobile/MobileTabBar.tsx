import type { ReactNode } from 'react'

export type MobileTabItem = {
  id: string
  label: string
  icon?: ReactNode
}

type MobileTabBarProps = {
  items: MobileTabItem[]
  activeId: string
  onChange: (id: string) => void
  ariaLabel?: string
}

export function MobileTabBar({
  items,
  activeId,
  onChange,
  ariaLabel = '底部导航',
}: MobileTabBarProps) {
  return (
    <nav className="mobile-tabbar" aria-label={ariaLabel}>
      <ul className="mobile-tabbar-list" style={{ gridTemplateColumns: `repeat(${Math.max(1, items.length)}, minmax(0, 1fr))` }}>
        {items.map((item) => {
          const selected = item.id === activeId
          return (
            <li key={item.id} className="mobile-tabbar-item">
              <button
                type="button"
                className={`mobile-tabbar-button ${selected ? 'active' : ''}`.trim()}
                aria-current={selected ? 'page' : undefined}
                onClick={() => onChange(item.id)}
              >
                {item.icon ? <span className="mobile-tabbar-icon">{item.icon}</span> : null}
                <span className="mobile-tabbar-label">{item.label}</span>
              </button>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
