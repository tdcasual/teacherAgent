import type { MutableRefObject, ReactNode } from 'react'

type TeacherAdminPanelProps = {
  panelRef: MutableRefObject<HTMLDivElement | null>
  authed: boolean
  authSubjectLabel: string
  onOpenModelSettingsPanel: () => void
  onClose: () => void
  children: ReactNode
}

export default function TeacherAdminPanel({
  panelRef,
  authed,
  authSubjectLabel,
  onOpenModelSettingsPanel,
  onClose,
  children,
}: TeacherAdminPanelProps) {
  return (
    <div
      ref={panelRef}
      className="absolute right-0 top-[calc(100%+8px)] z-40 grid w-[min(344px,calc(100vw-16px))] max-h-[min(80vh,720px)] max-w-[calc(100vw-16px)] gap-3 overflow-y-auto rounded-[18px] border border-[color:color-mix(in_oklab,var(--color-border)_82%,white)] bg-[linear-gradient(180deg,color-mix(in_oklab,var(--color-surface)_98%,white)_0%,color-mix(in_oklab,var(--color-surface-soft)_84%,white)_100%)] p-3 shadow-[0_12px_28px_rgba(15,23,42,0.12)]"
      role="dialog"
      aria-label="教师管理面板"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="grid gap-1">
          <div className="inline-flex w-fit items-center rounded-full border border-[color:color-mix(in_oklab,var(--color-border)_76%,white)] bg-[color:color-mix(in_oklab,var(--color-panel)_86%,white)] px-2.5 py-1 text-[11px] font-semibold tracking-[0.12em] text-muted">
            工具抽屉
          </div>
          <div className="text-sm font-semibold">教师管理</div>
          <div className="text-xs text-muted">
            {authed ? `已认证：${authSubjectLabel || '教师'}` : '当前未认证，请先完成教师认证。'}
          </div>
        </div>
        <button type="button" className="ghost" onClick={onClose}>
          收起
        </button>
      </div>

      <div className="flex items-center justify-between gap-3 rounded-[14px] bg-[color:color-mix(in_oklab,var(--color-panel)_88%,white)] px-3 py-2.5">
        <div className="text-xs text-muted">模型、认证和密码操作集中在这里。</div>
        <button type="button" className="teacher-drawer-link justify-start" onClick={onOpenModelSettingsPanel}>
          模型设置
        </button>
      </div>

      {children}
    </div>
  )
}
