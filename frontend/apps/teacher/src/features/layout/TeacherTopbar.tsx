import type { MutableRefObject } from 'react'

type TeacherTopbarProps = {
  topbarRef: MutableRefObject<HTMLElement | null>
  sessionSidebarOpen: boolean
  skillsOpen: boolean
  onToggleSessionSidebar: () => void
  onOpenRoutingSettingsPanel: () => void
  onToggleSkillsWorkbench: () => void
  onToggleSettingsPanel: () => void
}

export default function TeacherTopbar({
  topbarRef,
  sessionSidebarOpen,
  skillsOpen,
  onToggleSessionSidebar,
  onOpenRoutingSettingsPanel,
  onToggleSkillsWorkbench,
  onToggleSettingsPanel,
}: TeacherTopbarProps) {
  return (
    <header
      ref={topbarRef}
      className="flex justify-between items-center gap-[12px] px-4 py-[10px] bg-white/[0.94] border-b border-border sticky top-0 z-[25]"
      style={{ backdropFilter: 'saturate(180%) blur(8px)' }}
    >
      <div className="flex items-center gap-[10px] flex-wrap">
        <div className="font-bold text-[16px] tracking-[0.2px]">物理教学助手 · 老师端</div>
        <button className="ghost" type="button" onClick={onToggleSessionSidebar}>
          {sessionSidebarOpen ? '收起会话' : '展开会话'}
        </button>
      </div>
      <div className="flex gap-[10px] items-center flex-wrap">
        <div className="role-badge teacher">身份：老师</div>
        <button className="ghost" type="button" onClick={onOpenRoutingSettingsPanel}>
          模型路由
        </button>
        <button className="ghost" type="button" onClick={onToggleSkillsWorkbench}>
          {skillsOpen ? '收起工作台' : '打开工作台'}
        </button>
        <button
          className="ghost border-none bg-transparent cursor-pointer p-[6px] rounded-lg text-[#6b7280] transition-[background] duration-150 ease-in-out hover:bg-surface-soft [&_svg]:block"
          onClick={onToggleSettingsPanel}
          aria-label="设置"
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
        </button>
      </div>
    </header>
  )
}
