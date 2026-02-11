import { useCallback, useRef, type KeyboardEvent } from 'react'
import { getNextMenuIndex } from '../../../../shared/sessionMenuNavigation'

type HistorySessionItem = {
  session_id: string
  updated_at?: string
  preview?: string
  message_count?: number
}

type HistorySessionGroup = {
  key: string
  label: string
  items: HistorySessionItem[]
}

type Props = {
  open: boolean
  historyQuery: string
  historyLoading: boolean
  historyError: string
  showArchivedSessions: boolean
  visibleHistoryCount: number
  groupedHistorySessions: HistorySessionGroup[]
  activeSessionId: string
  openSessionMenuId: string
  deletedSessionIds: string[]
  historyHasMore: boolean
  sessionHasMore: boolean
  sessionLoading: boolean
  sessionError: string
  onStartNewSession: () => void
  onRefreshSessions: (mode?: 'more') => void
  onToggleArchived: () => void
  onHistoryQueryChange: (value: string) => void
  onSelectSession: (sessionId: string) => void
  onToggleSessionMenu: (sessionId: string) => void
  onRenameSession: (sessionId: string) => void
  onToggleSessionArchive: (sessionId: string) => void
  onLoadOlderMessages: () => void
  getSessionTitle: (sessionId: string) => string
  formatSessionUpdatedLabel: (updatedAt?: string) => string
}

export default function SessionSidebar({
  open,
  historyQuery,
  historyLoading,
  historyError,
  showArchivedSessions,
  visibleHistoryCount,
  groupedHistorySessions,
  activeSessionId,
  openSessionMenuId,
  deletedSessionIds,
  historyHasMore,
  sessionHasMore,
  sessionLoading,
  sessionError,
  onStartNewSession,
  onRefreshSessions,
  onToggleArchived,
  onHistoryQueryChange,
  onSelectSession,
  onToggleSessionMenu,
  onRenameSession,
  onToggleSessionArchive,
  onLoadOlderMessages,
  getSessionTitle,
  formatSessionUpdatedLabel,
}: Props) {
  const menuRefs = useRef<Record<string, HTMLDivElement | null>>({})
  const triggerRefs = useRef<Record<string, HTMLButtonElement | null>>({})

  const toDomSafeId = useCallback((value: string) => String(value || '').replace(/[^a-zA-Z0-9_-]/g, '_'), [])

  const setMenuRef = useCallback((sessionId: string, node: HTMLDivElement | null) => {
    const sid = String(sessionId || '').trim()
    if (!sid) return
    if (node) {
      menuRefs.current[sid] = node
      return
    }
    delete menuRefs.current[sid]
  }, [])

  const setTriggerRef = useCallback((sessionId: string, node: HTMLButtonElement | null) => {
    const sid = String(sessionId || '').trim()
    if (!sid) return
    if (node) {
      triggerRefs.current[sid] = node
      return
    }
    delete triggerRefs.current[sid]
  }, [])

  const focusMenuItem = useCallback((sessionId: string, target: 'first' | 'last') => {
    const sid = String(sessionId || '').trim()
    if (!sid) return
    const menu = menuRefs.current[sid]
    if (!menu) return
    const items = Array.from(menu.querySelectorAll<HTMLButtonElement>('[data-session-menu-item]:not([disabled])'))
    if (!items.length) return
    const index = target === 'last' ? items.length - 1 : 0
    items[index]?.focus()
  }, [])

  const handleTriggerKeyDown = useCallback(
    (sessionId: string, isMenuOpen: boolean, event: KeyboardEvent<HTMLButtonElement>) => {
      const sid = String(sessionId || '').trim()
      if (!sid) return
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault()
        event.stopPropagation()
        if (!isMenuOpen) onToggleSessionMenu(sid)
        const target: 'first' | 'last' = event.key === 'ArrowUp' ? 'last' : 'first'
        window.setTimeout(() => focusMenuItem(sid, target), 0)
        return
      }
      if (event.key === 'Escape' && isMenuOpen) {
        event.preventDefault()
        onToggleSessionMenu(sid)
      }
    },
    [focusMenuItem, onToggleSessionMenu],
  )

  const handleMenuKeyDown = useCallback(
    (sessionId: string, event: KeyboardEvent<HTMLDivElement>) => {
      const sid = String(sessionId || '').trim()
      if (!sid) return
      const menu = menuRefs.current[sid]
      if (!menu) return

      const items = Array.from(menu.querySelectorAll<HTMLButtonElement>('[data-session-menu-item]:not([disabled])'))
      if (!items.length) return
      const activeIndex = items.findIndex((item) => item === document.activeElement)

      if (event.key === 'Escape') {
        event.preventDefault()
        onToggleSessionMenu(sid)
        triggerRefs.current[sid]?.focus()
        return
      }
      if (event.key === 'Tab') {
        onToggleSessionMenu(sid)
        return
      }

      let direction: 'next' | 'prev' | 'first' | 'last' | null = null
      if (event.key === 'ArrowDown') direction = 'next'
      else if (event.key === 'ArrowUp') direction = 'prev'
      else if (event.key === 'Home') direction = 'first'
      else if (event.key === 'End') direction = 'last'
      if (!direction) return

      event.preventDefault()
      const nextIndex = getNextMenuIndex(activeIndex, items.length, direction)
      if (nextIndex >= 0) items[nextIndex]?.focus()
    },
    [onToggleSessionMenu],
  )

  return (
    <aside className={`session-sidebar border-r border-border bg-[#fbfbfc] p-2.5 flex flex-col gap-2 min-h-0 overflow-hidden transition-all duration-150 ease-in-out ${open ? 'open' : 'collapsed'}`}>
      <div className="flex justify-between items-center gap-[6px] flex-none">
        <strong>历史会话</strong>
        <div className="flex items-center gap-[6px]">
          <button type="button" className="ghost" onClick={onStartNewSession}>
            新建
          </button>
          <button type="button" className="ghost" disabled={historyLoading} onClick={() => onRefreshSessions()}>
            {historyLoading ? '刷新中…' : '刷新'}
          </button>
          <button type="button" className="ghost" onClick={onToggleArchived}>
            {showArchivedSessions ? '查看会话' : '查看归档'}
          </button>
        </div>
      </div>
      <div className="grid gap-[6px] flex-none">
        <input value={historyQuery} onChange={(e) => onHistoryQueryChange(e.target.value)} placeholder="搜索会话" className="px-2.5 py-2 rounded-[12px] text-[13px]" />
      </div>
      {historyError ? <div className="status err">{historyError}</div> : null}
      {!historyLoading && visibleHistoryCount === 0 ? (
        <div className="text-xs text-muted">{showArchivedSessions ? '暂无归档会话。' : '暂无历史会话。'}</div>
      ) : null}
      <div className="session-groups flex flex-col gap-2 overflow-auto min-h-0 flex-1 pr-1 content-start" style={{ overscrollBehavior: 'contain' }}>
        {groupedHistorySessions.map((group) => (
          <div key={group.key} className="flex flex-col gap-1">
            <div className="text-[12px] text-muted px-[2px]">{group.label}</div>
            <div className="flex flex-col gap-[6px]">
              {group.items.map((item) => {
                const sid = item.session_id || 'main'
                const isActive = sid === activeSessionId
                const isMenuOpen = sid === openSessionMenuId
                const isArchived = deletedSessionIds.includes(sid)
                const menuDomIdBase = `teacher-session-menu-${toDomSafeId(sid)}`
                const menuId = `${menuDomIdBase}-list`
                const triggerId = `${menuDomIdBase}-trigger`
                const updatedLabel = formatSessionUpdatedLabel(item.updated_at)
                return (
                  <div key={sid} className={`session-item border border-border bg-white px-2.5 py-2 rounded-[12px] relative transition-all duration-150 ease-in-out hover:border-[#cfd4dc] hover:bg-[#fcfcfd] ${isActive ? 'active border-[#86d6c4] bg-[#f4fbf8]' : ''}`}>
                    <button type="button" className="session-select w-full border-none bg-transparent pr-7 pl-0 py-0 text-left cursor-pointer block" onClick={() => onSelectSession(sid)}>
                      <div className="grid gap-[2px]">
                        <div className="session-id text-[13px] font-semibold text-ink leading-[1.35] whitespace-nowrap overflow-hidden text-ellipsis">{getSessionTitle(sid)}</div>
                        <div className="text-[11px] text-muted leading-[1.3]">
                          {(item.message_count || 0).toString()} 条{updatedLabel ? ` · ${updatedLabel}` : ''}
                        </div>
                      </div>
                      {item.preview ? <div className="text-[12px] text-muted mt-[3px] whitespace-nowrap overflow-hidden text-ellipsis">{item.preview}</div> : null}
                    </button>
                    <div className="session-menu-wrap absolute top-[6px] right-[6px]">
                      <button
                        type="button"
                        id={triggerId}
                        ref={(node) => setTriggerRef(sid, node)}
                        className="session-menu-trigger w-[22px] h-[22px] border border-transparent rounded-full bg-transparent text-[#6b7280] cursor-pointer grid place-items-center text-[16px] leading-none hover:bg-surface-soft hover:border-border hover:text-[#374151]"
                        aria-haspopup="menu"
                        aria-expanded={isMenuOpen}
                        aria-controls={menuId}
                        aria-label={`会话 ${getSessionTitle(sid)} 操作`}
                        onClick={(e) => {
                          e.stopPropagation()
                          onToggleSessionMenu(sid)
                        }}
                        onKeyDown={(event) => handleTriggerKeyDown(sid, isMenuOpen, event)}
                      >
                        ⋯
                      </button>
                      {isMenuOpen ? (
                        <div
                          id={menuId}
                          ref={(node) => setMenuRef(sid, node)}
                          className="session-menu absolute top-[26px] right-0 min-w-[102px] border border-border rounded-[10px] bg-white shadow-sm p-1 grid gap-[2px] z-[2]"
                          role="menu"
                          aria-orientation="vertical"
                          aria-labelledby={triggerId}
                          onKeyDown={(event) => handleMenuKeyDown(sid, event)}
                        >
                          <button type="button" role="menuitem" data-session-menu-item className="session-menu-item border-none bg-transparent rounded-lg px-[9px] py-[7px] text-[12px] text-left text-[#374151] cursor-pointer hover:bg-surface-soft" onClick={() => onRenameSession(sid)}>
                            重命名
                          </button>
                          <button
                            type="button"
                            role="menuitem"
                            data-session-menu-item
                            className={`session-menu-item border-none bg-transparent rounded-lg px-[9px] py-[7px] text-[12px] text-left cursor-pointer ${isArchived ? 'text-[#374151] hover:bg-surface-soft' : 'text-[#b42318] hover:bg-[#fff1f1]'}`}
                            onClick={() => onToggleSessionArchive(sid)}
                          >
                            {isArchived ? '恢复' : '归档'}
                          </button>
                        </div>
                      ) : null}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        ))}
      </div>
      <div className="flex gap-2.5 items-start flex-wrap flex-none">
        <button type="button" className="ghost" disabled={!historyHasMore || historyLoading} onClick={() => onRefreshSessions('more')}>
          {historyLoading ? '加载中…' : historyHasMore ? '加载更多会话' : '已显示全部会话'}
        </button>
      </div>
      <div className="flex gap-2.5 items-start flex-wrap flex-none">
        <button type="button" className="ghost" disabled={!sessionHasMore || sessionLoading} onClick={onLoadOlderMessages}>
          {sessionLoading ? '加载中…' : sessionHasMore ? '加载更早消息' : '没有更早消息'}
        </button>
        {sessionError ? <div className="status err">{sessionError}</div> : null}
      </div>
    </aside>
  )
}
