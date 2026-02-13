import { formatSessionUpdatedLabel } from '../../../../shared/time'
import type { SessionSidebarProps } from './sessionSidebarTypes'

const toDomSafeId = (value: string) => String(value || '').replace(/[^a-zA-Z0-9_-]/g, '_')

type Props = Pick<
SessionSidebarProps,
| 'dispatch'
| 'verifiedStudent'
| 'historyLoading'
| 'historyError'
| 'historyHasMore'
| 'refreshSessions'
| 'showArchivedSessions'
| 'historyQuery'
| 'visibleSessionCount'
| 'groupedSessions'
| 'deletedSessionIds'
| 'activeSessionId'
| 'onSelectSession'
| 'getSessionTitle'
| 'openSessionMenuId'
| 'toggleSessionMenu'
| 'handleSessionMenuTriggerKeyDown'
| 'handleSessionMenuKeyDown'
| 'setSessionMenuTriggerRef'
| 'setSessionMenuRef'
| 'renameSession'
| 'toggleSessionArchive'
| 'sessionHasMore'
| 'sessionLoading'
| 'sessionCursor'
| 'loadSessionMessages'
| 'sessionError'
| 'startNewStudentSession'
>

export default function SessionSidebarHistorySection(props: Props) {
  const {
    dispatch, verifiedStudent, historyLoading, historyError, historyHasMore, refreshSessions,
    showArchivedSessions, historyQuery, visibleSessionCount, groupedSessions, deletedSessionIds,
    activeSessionId, onSelectSession, getSessionTitle, openSessionMenuId, toggleSessionMenu,
    handleSessionMenuTriggerKeyDown, handleSessionMenuKeyDown, setSessionMenuTriggerRef,
    setSessionMenuRef, renameSession, toggleSessionArchive, sessionHasMore, sessionLoading,
    sessionCursor, loadSessionMessages, sessionError, startNewStudentSession,
  } = props

  return (
    <>
      <div className="flex justify-between items-center gap-1.5 max-[900px]:sticky max-[900px]:top-0 max-[900px]:z-1 max-[900px]:bg-white max-[900px]:pb-1.5">
        <strong>历史会话</strong>
        <div className="flex items-center gap-1.5 [&_.ghost]:px-[9px] [&_.ghost]:py-1 [&_.ghost]:text-[11px]">
          <button type="button" className="ghost" onClick={startNewStudentSession}>新建</button>
          <button type="button" className="ghost" disabled={!verifiedStudent || historyLoading} onClick={() => void refreshSessions()}>
            {historyLoading ? '刷新中…' : '刷新'}
          </button>
          <button type="button" className="ghost" disabled={!verifiedStudent} onClick={() => dispatch({ type: 'SET', field: 'showArchivedSessions', value: !showArchivedSessions })}>
            {showArchivedSessions ? '查看会话' : '查看归档'}
          </button>
        </div>
      </div>
      <div className="grid gap-1.5 max-[900px]:sticky max-[900px]:top-[34px] max-[900px]:z-1 max-[900px]:bg-white max-[900px]:pb-1">
        <input className="!px-2.5 !py-2 !rounded-[10px] !text-[13px]" value={historyQuery} onChange={(e) => dispatch({ type: 'SET', field: 'historyQuery', value: e.target.value })} placeholder="搜索会话" disabled={!verifiedStudent} />
      </div>
      {!verifiedStudent && <div className="text-xs text-muted">请先完成姓名验证后查看历史记录。</div>}
      {historyError && <div className="status err">{historyError}</div>}
      {verifiedStudent && !historyLoading && visibleSessionCount === 0 && !historyError && (
        <div className="text-xs text-muted">{showArchivedSessions ? '暂无归档会话。' : '暂无历史记录。'}</div>
      )}
      <div className="session-groups flex flex-col gap-2 overflow-auto min-h-0 flex-1 pr-1">
        {groupedSessions.map((group) => (
          <div key={group.key} className="flex flex-col gap-1">
            <div className="text-xs text-muted px-0.5">{group.label}</div>
            <div className="flex flex-col gap-1.5">
              {group.items.map((item) => {
                const sid = item.session_id
                const isActive = sid === activeSessionId
                const isMenuOpen = sid === openSessionMenuId
                const isArchived = deletedSessionIds.includes(sid)
                const menuDomIdBase = `student-session-menu-${toDomSafeId(sid)}`
                const menuId = `${menuDomIdBase}-list`
                const triggerId = `${menuDomIdBase}-trigger`
                const updatedLabel = formatSessionUpdatedLabel(item.updated_at)
                return (
                  <div
                    key={sid}
                    className={`session-item relative rounded-xl border px-2.5 py-2 transition-[border-color,background] duration-150 max-[900px]:px-[9px] max-[900px]:py-2 ${
                      isActive ? 'border-[#86d6c4] bg-[#f4fbf8]' : 'border-border bg-white hover:border-[#cfd4dc] hover:bg-[#fcfcfd]'
                    } ${isActive ? 'active' : ''}`}
                  >
                    <button type="button" className="session-select w-full border-none bg-transparent pr-7 text-left cursor-pointer block" onClick={() => onSelectSession(sid)}>
                      <div className="grid gap-0.5">
                        <div className="session-id text-[13px] font-semibold text-ink leading-[1.35] whitespace-nowrap overflow-hidden text-ellipsis">{getSessionTitle(sid)}</div>
                        <div className="text-[11px] text-muted leading-[1.3]">
                          {(item.message_count || 0).toString()} 条{updatedLabel ? ` · ${updatedLabel}` : ''}
                        </div>
                      </div>
                      {item.preview ? <div className="text-xs text-muted mt-0.5 whitespace-nowrap overflow-hidden text-ellipsis">{item.preview}</div> : null}
                    </button>
                    <div className="session-menu-wrap absolute top-1.5 right-1.5">
                      <button
                        type="button"
                        id={triggerId}
                        ref={(node) => setSessionMenuTriggerRef(sid, node)}
                        className="session-menu-trigger w-[22px] h-[22px] border border-transparent rounded-full bg-transparent text-[#6b7280] cursor-pointer grid place-items-center text-base leading-none hover:bg-surface-soft hover:border-border hover:text-[#374151] aria-expanded:bg-surface-soft aria-expanded:border-border aria-expanded:text-[#374151]"
                        aria-haspopup="menu"
                        aria-expanded={isMenuOpen}
                        aria-controls={menuId}
                        aria-label={`会话 ${getSessionTitle(sid)} 操作`}
                        onClick={(e) => { e.stopPropagation(); toggleSessionMenu(sid) }}
                        onKeyDown={(event) => handleSessionMenuTriggerKeyDown(sid, isMenuOpen, event)}
                      >
                        ⋯
                      </button>
                      {isMenuOpen ? (
                        <div
                          id={menuId}
                          ref={(node) => setSessionMenuRef(sid, node)}
                          className="session-menu absolute top-[26px] right-0 min-w-[102px] border border-border rounded-[10px] bg-white shadow-sm p-1 grid gap-0.5 z-2 max-[900px]:min-w-[112px]"
                          role="menu"
                          aria-orientation="vertical"
                          aria-labelledby={triggerId}
                          onKeyDown={(event) => handleSessionMenuKeyDown(sid, event)}
                        >
                          <button type="button" role="menuitem" className="session-menu-item border-none bg-transparent rounded-lg px-[9px] py-[7px] text-xs text-left text-[#374151] cursor-pointer hover:bg-surface-soft" onClick={() => renameSession(sid)}>
                            重命名
                          </button>
                          <button type="button" role="menuitem" className={`session-menu-item border-none bg-transparent rounded-lg px-[9px] py-[7px] text-xs text-left cursor-pointer ${isArchived ? 'text-[#374151] hover:bg-surface-soft' : 'text-[#b42318] hover:bg-[#fff1f1]'}`} onClick={() => toggleSessionArchive(sid)}>
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
      {verifiedStudent && (
        <div className="flex gap-2 items-start flex-wrap">
          <button type="button" className="ghost" disabled={!historyHasMore || historyLoading} onClick={() => void refreshSessions('more')}>
            {historyLoading ? '加载中…' : historyHasMore ? '加载更多会话' : '已显示全部会话'}
          </button>
        </div>
      )}
      {verifiedStudent && activeSessionId && (
        <div className="flex gap-2 items-start flex-wrap">
          <button type="button" className="ghost" disabled={!sessionHasMore || sessionLoading} onClick={() => void loadSessionMessages(activeSessionId, sessionCursor, true)}>
            {sessionLoading ? '加载中…' : sessionHasMore ? '加载更早消息' : '没有更早消息'}
          </button>
          {sessionError && <div className="status err">{sessionError}</div>}
        </div>
      )}
    </>
  )
}
