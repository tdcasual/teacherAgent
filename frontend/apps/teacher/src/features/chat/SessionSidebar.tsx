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
    const items = Array.from(menu.querySelectorAll<HTMLButtonElement>('.session-menu-item:not([disabled])'))
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

      const items = Array.from(menu.querySelectorAll<HTMLButtonElement>('.session-menu-item:not([disabled])'))
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
    <aside className={`session-sidebar ${open ? 'open' : 'collapsed'}`}>
      <div className="session-sidebar-header">
        <strong>历史会话</strong>
        <div className="session-sidebar-actions">
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
      <div className="session-search">
        <input value={historyQuery} onChange={(e) => onHistoryQueryChange(e.target.value)} placeholder="搜索会话" />
      </div>
      {historyError ? <div className="status err">{historyError}</div> : null}
      {!historyLoading && visibleHistoryCount === 0 ? (
        <div className="history-hint">{showArchivedSessions ? '暂无归档会话。' : '暂无历史会话。'}</div>
      ) : null}
      <div className="session-groups">
        {groupedHistorySessions.map((group) => (
          <div key={group.key} className="session-group">
            <div className="session-group-title">{group.label}</div>
            <div className="session-list">
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
                  <div key={sid} className={`session-item ${isActive ? 'active' : ''}`}>
                    <button type="button" className="session-select" onClick={() => onSelectSession(sid)}>
                      <div className="session-main">
                        <div className="session-id">{getSessionTitle(sid)}</div>
                        <div className="session-meta">
                          {(item.message_count || 0).toString()} 条{updatedLabel ? ` · ${updatedLabel}` : ''}
                        </div>
                      </div>
                      {item.preview ? <div className="session-preview">{item.preview}</div> : null}
                    </button>
                    <div className="session-menu-wrap">
                      <button
                        type="button"
                        id={triggerId}
                        ref={(node) => setTriggerRef(sid, node)}
                        className="session-menu-trigger"
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
                          className="session-menu"
                          role="menu"
                          aria-orientation="vertical"
                          aria-labelledby={triggerId}
                          onKeyDown={(event) => handleMenuKeyDown(sid, event)}
                        >
                          <button type="button" role="menuitem" className="session-menu-item" onClick={() => onRenameSession(sid)}>
                            重命名
                          </button>
                          <button
                            type="button"
                            role="menuitem"
                            className={`session-menu-item${isArchived ? '' : ' danger'}`}
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
      <div className="history-footer">
        <button type="button" className="ghost" disabled={!historyHasMore || historyLoading} onClick={() => onRefreshSessions('more')}>
          {historyLoading ? '加载中…' : historyHasMore ? '加载更多会话' : '已显示全部会话'}
        </button>
      </div>
      <div className="history-footer">
        <button type="button" className="ghost" disabled={!sessionHasMore || sessionLoading} onClick={onLoadOlderMessages}>
          {sessionLoading ? '加载中…' : sessionHasMore ? '加载更早消息' : '没有更早消息'}
        </button>
        {sessionError ? <div className="status err">{sessionError}</div> : null}
      </div>
    </aside>
  )
}
