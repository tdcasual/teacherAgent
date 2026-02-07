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
                        className="session-menu-trigger"
                        aria-haspopup="menu"
                        aria-expanded={isMenuOpen}
                        aria-label={`会话 ${getSessionTitle(sid)} 操作`}
                        onClick={(e) => {
                          e.stopPropagation()
                          onToggleSessionMenu(sid)
                        }}
                      >
                        ⋯
                      </button>
                      {isMenuOpen ? (
                        <div className="session-menu" role="menu">
                          <button type="button" className="session-menu-item" onClick={() => onRenameSession(sid)}>
                            重命名
                          </button>
                          <button
                            type="button"
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
