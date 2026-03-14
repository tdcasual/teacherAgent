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
      className="absolute right-0 top-[calc(100%+8px)] z-40 grid w-[min(360px,calc(100vw-16px))] max-h-[min(80vh,720px)] max-w-[calc(100vw-16px)] gap-2.5 overflow-y-auto rounded-xl border border-border bg-white p-3 shadow-[0_12px_28px_rgba(15,23,42,0.14)]"
      role="dialog"
      aria-label="教师管理面板"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="grid gap-1">
          <div className="text-sm font-semibold">教师管理</div>
          <div className="text-xs text-muted">
            {authed ? `已认证：${authSubjectLabel || '教师'}` : '当前未认证，请先完成教师认证。'}
          </div>
        </div>
        <button type="button" className="ghost" onClick={onClose}>
          收起
        </button>
      </div>

      <div className="grid gap-2 rounded-[10px] border border-border bg-surface-soft p-2.5">
        <div className="text-xs text-muted">模型与教务相关入口统一收纳到这里，减少顶栏拥挤。</div>
        <button type="button" className="ghost justify-start" onClick={onOpenModelSettingsPanel}>
          模型设置
        </button>
      </div>

      {children}
    </div>
  )
}
