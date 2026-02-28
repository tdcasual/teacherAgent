import { useCallback, useRef, type KeyboardEvent, type ReactNode } from 'react'

export type MobileTabItem = {
  id: string
  label: string
  icon?: ReactNode
  panelId?: string
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
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([])
  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
      if (!items.length) return
      let nextIndex = -1
      if (event.key === 'ArrowRight') nextIndex = (index + 1) % items.length
      else if (event.key === 'ArrowLeft') nextIndex = (index - 1 + items.length) % items.length
      else if (event.key === 'Home') nextIndex = 0
      else if (event.key === 'End') nextIndex = items.length - 1
      if (nextIndex < 0) return
      event.preventDefault()
      onChange(items[nextIndex].id)
      tabRefs.current[nextIndex]?.focus()
    },
    [items, onChange],
  )

  return (
    <nav className="mobile-tabbar" aria-label={ariaLabel}>
      <ul
        className="mobile-tabbar-list"
        role="tablist"
        aria-orientation="horizontal"
        style={{ gridTemplateColumns: `repeat(${Math.max(1, items.length)}, minmax(0, 1fr))` }}
      >
        {items.map((item, index) => {
          const selected = item.id === activeId
          return (
            <li key={item.id} className="mobile-tabbar-item">
              <button
                type="button"
                ref={(node) => {
                  tabRefs.current[index] = node
                }}
                className={`mobile-tabbar-button ${selected ? 'active' : ''}`.trim()}
                role="tab"
                id={`mobile-tab-${item.id}`}
                aria-selected={selected}
                tabIndex={selected ? 0 : -1}
                aria-controls={item.panelId}
                aria-current={selected ? 'page' : undefined}
                onKeyDown={(event) => handleKeyDown(event, index)}
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
