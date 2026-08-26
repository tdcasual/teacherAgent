import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { MutableRefObject } from 'react'

import { useDismissibleLayer } from '../../../../shared/useDismissibleLayer'

type TeacherTopbarOverflowMenuProps = {
  skillsOpen: boolean
  authOpen: boolean
  authButtonRef: MutableRefObject<HTMLButtonElement | null>
  onToggleAuth: () => void
  onToggleSkillsWorkbench: () => void
  onToggleSettingsPanel: () => void
}

export default function TeacherTopbarOverflowMenu({
  skillsOpen,
  authOpen,
  authButtonRef,
  onToggleAuth,
  onToggleSkillsWorkbench,
  onToggleSettingsPanel,
}: TeacherTopbarOverflowMenuProps) {
  const quickActionsButtonRef = useRef<HTMLButtonElement | null>(null)
  const quickActionsPanelRef = useRef<HTMLDivElement | null>(null)
  const [quickActionsOpen, setQuickActionsOpen] = useState(false)
  const closeQuickActions = useCallback(() => setQuickActionsOpen(false), [])
  const quickActionsLayerRefs = useMemo(
    () => [quickActionsPanelRef, quickActionsButtonRef] as const,
    [],
  )

  useEffect(() => {
    if (authOpen && quickActionsOpen) setQuickActionsOpen(false)
  }, [authOpen, quickActionsOpen])

  useDismissibleLayer({
    open: quickActionsOpen,
    onDismiss: closeQuickActions,
    refs: quickActionsLayerRefs,
  })

  return (
    <>
      <button
        ref={quickActionsButtonRef}
        className="ghost"
        type="button"
        aria-haspopup="menu"
        aria-expanded={quickActionsOpen}
        onClick={() => setQuickActionsOpen((prev) => !prev)}
      >
        更多
      </button>
      {quickActionsOpen ? (
        <div
          ref={quickActionsPanelRef}
          className="absolute right-0 top-[calc(100%+8px)] z-40 min-w-[180px] rounded-xl border border-border bg-white p-2 shadow-[0_12px_28px_rgba(15,23,42,0.14)] grid gap-1"
          role="menu"
          aria-label="移动端更多操作"
        >
          <button
            ref={authButtonRef}
            className="ghost justify-start"
            type="button"
            aria-haspopup="dialog"
            aria-expanded={authOpen}
            onClick={() => {
              onToggleAuth()
              setQuickActionsOpen(false)
            }}
          >
            打开管理
          </button>
          <button
            className="ghost justify-start"
            type="button"
            onClick={() => {
              onToggleSkillsWorkbench()
              setQuickActionsOpen(false)
            }}
          >
            {skillsOpen ? '收起工作台' : '打开工作台'}
          </button>
          <button
            className="ghost justify-start"
            type="button"
            onClick={() => {
              onToggleSettingsPanel()
              setQuickActionsOpen(false)
            }}
          >
            打开设置
          </button>
        </div>
      ) : null}
    </>
  )
}
