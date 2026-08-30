import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { createRef, type ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import TeacherAppLayout, { type TeacherAppLayoutProps } from './TeacherAppLayout'
import type { TeacherWorkbenchViewModel } from '../workbench/teacherWorkbenchViewModel'

vi.mock('./TeacherTopbar', () => ({
  default: () => <header data-testid="teacher-topbar">topbar</header>,
}))

vi.mock('../settings/TeacherSettingsPanel', () => ({
  default: ({ open }: { open: boolean }) => (open ? <div data-testid="teacher-settings">settings</div> : null),
}))

vi.mock('../chat/TeacherSessionRail', () => ({
  default: () => <div data-testid="teacher-session-rail">rail</div>,
}))

vi.mock('../chat/SessionSidebar', () => ({
  default: () => <div data-testid="session-sidebar">sidebar</div>,
}))

vi.mock('../chat/TeacherChatMainContent', () => ({
  default: () => <div data-testid="teacher-chat">chat</div>,
}))

vi.mock('../workbench/TeacherWorkbench', () => ({
  default: () => <div data-testid="teacher-workbench">workbench</div>,
}))

vi.mock('../../../../shared/dialog', () => ({
  PromptDialog: ({ open, title }: { open: boolean; title: string }) =>
    open ? <div data-testid="prompt-dialog">{title}</div> : null,
  ConfirmDialog: ({ open, title }: { open: boolean; title: string }) =>
    open ? <div data-testid="confirm-dialog">{title}</div> : null,
}))

vi.mock('../../../../shared/mobile/BottomSheet', () => ({
  BottomSheet: ({
    open,
    title,
    onClose,
    children,
  }: {
    open: boolean
    title: string
    onClose: () => void
    children: ReactNode
  }) =>
    open ? (
      <div data-testid={`bottom-sheet-${title}`}>
        <button type="button" onClick={onClose}>
          close-{title}
        </button>
        {children}
      </div>
    ) : null,
}))

vi.mock('../../../../shared/mobile/MobileTabBar', () => ({
  MobileTabBar: ({ activeId }: { activeId: string }) => <nav data-testid="mobile-tab-bar">{activeId}</nav>,
}))

vi.mock('react-resizable-panels', () => ({
  Group: ({ children, className }: { children: ReactNode; className?: string }) => (
    <div data-testid="panel-group" className={className}>
      {children}
    </div>
  ),
  Panel: ({ children }: { children: ReactNode }) => <div data-testid="panel">{children}</div>,
  Separator: ({ children }: { children?: ReactNode }) => <div data-testid="panel-separator">{children}</div>,
}))

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const noop = () => undefined

const buildSessionSidebar = (): TeacherAppLayoutProps['sessionSidebar'] => ({
  historyQuery: '',
  historyLoading: false,
  historyError: '',
  showArchivedSessions: false,
  visibleHistoryCount: 0,
  groupedHistorySessions: [],
  activeSessionId: 'main',
  openSessionMenuId: '',
  deletedSessionIds: [],
  historyHasMore: false,
  sessionHasMore: false,
  sessionLoading: false,
  sessionError: '',
  onStartNewSession: noop,
  onRefreshSessions: noop,
  onToggleArchived: noop,
  onHistoryQueryChange: noop,
  onToggleSessionMenu: noop,
  onRenameSession: noop,
  onToggleSessionArchive: noop,
  onLoadOlderMessages: noop,
  getSessionTitle: (sessionId: string) => sessionId,
})

const buildChat = (): TeacherAppLayoutProps['chat'] => ({
  renderedMessages: [],
  sending: false,
  hasPendingChatJob: false,
  typingTimeLabel: '10:00',
  messagesRef: { current: null },
  onMessagesScroll: noop,
  showScrollToBottom: false,
  onScrollToBottom: noop,
  activeSkillId: 'teacher-assignment-ops',
  skillPinned: false,
  input: '',
  chatQueueHint: '',
  pendingStreamStage: '',
  pendingToolRuns: [],
  composerWarning: '',
  attachments: [],
  uploadingAttachments: false,
  hasSendableAttachments: false,
  inputRef: { current: null },
  onSubmit: noop,
  onInputChange: noop,
  onInputClick: noop,
  onInputKeyUp: noop,
  onInputKeyDown: noop,
  onPickFiles: noop,
  onRemoveAttachment: noop,
  mention: null,
  mentionIndex: 0,
  onInsertMention: noop,
})

const buildProps = (overrides: Partial<TeacherAppLayoutProps> = {}): TeacherAppLayoutProps => ({
  appRef: createRef<HTMLDivElement>(),
  topbarRef: createRef<HTMLElement>(),
  workbenchPanelRef: createRef(),
  topbarHeight: 64,
  teacherUseMobileShellV2: false,
  mobileShellV2Enabled: false,
  sessionSidebarOpen: true,
  skillsOpen: true,
  isMobileLayout: false,
  isWorkbenchResizing: false,
  workbenchMaxWidth: 620,
  initialWorkbenchWidth: 320,
  mobileTab: 'chat',
  setMobileTab: vi.fn(),
  settingsOpen: false,
  apiBase: 'http://localhost:8000',
  onApiBaseChange: noop,
  onCloseSettings: noop,
  onToggleSessionSidebar: noop,
  onOpenModelSettingsPanel: noop,
  onToggleSkillsWorkbench: noop,
  onToggleSettingsPanel: noop,
  startWorkbenchResize: noop,
  onWorkbenchResizeReset: noop,
  onMobileTabChange: noop,
  onSelectSessionFromSheet: noop,
  setSessionSidebarOpen: noop,
  setSkillsOpen: noop,
  setActiveSessionId: noop,
  setSessionCursor: noop,
  setSessionHasMore: noop,
  setSessionError: noop,
  setOpenSessionMenuId: noop,
  closeSessionSidebarOnMobile: noop,
  taskStrip: <div>task-strip</div>,
  workbenchViewModel: {} as TeacherWorkbenchViewModel,
  sessionSidebar: buildSessionSidebar(),
  chat: buildChat(),
  renameDialogSessionId: null,
  archiveDialogSessionId: null,
  archiveDialogActionLabel: '归档',
  archiveDialogIsArchived: false,
  onCancelRenameDialog: noop,
  onConfirmRenameDialog: noop,
  onCancelArchiveDialog: noop,
  onConfirmArchiveDialog: noop,
  ...overrides,
})

describe('TeacherAppLayout', () => {
  it('renders the desktop teacher shell with rail, chat, and workbench', async () => {
    render(<TeacherAppLayout {...buildProps()} />)

    const shell = document.querySelector('.app.teacher')
    expect(shell).toBeTruthy()
    expect(shell?.getAttribute('data-mobile-shell-v2')).toBe('0')
    expect(shell?.classList.contains('teacher-mobile-shell-v2')).toBe(false)
    expect(document.querySelector('.teacher-layout')).toBeTruthy()
    expect(screen.getByTestId('teacher-topbar')).toBeTruthy()
    expect(screen.getByTestId('teacher-session-rail')).toBeTruthy()
    expect(screen.getByTestId('teacher-chat')).toBeTruthy()
    expect(await screen.findAllByTestId('teacher-workbench')).toHaveLength(1)
    expect(screen.queryByTestId('mobile-tab-bar')).toBeNull()
    expect(screen.queryByTestId('bottom-sheet-历史会话')).toBeNull()
    expect(screen.queryByTestId('bottom-sheet-工作台')).toBeNull()
    expect(screen.queryByTestId('teacher-settings')).toBeNull()
  })

  it('lazy-loads settings only after the panel is opened', async () => {
    const { rerender } = render(<TeacherAppLayout {...buildProps({ settingsOpen: false })} />)
    expect(screen.queryByTestId('teacher-settings')).toBeNull()

    rerender(<TeacherAppLayout {...buildProps({ settingsOpen: true })} />)
    expect(await screen.findByTestId('teacher-settings')).toBeTruthy()
  })

  it('switches to mobile shell v2: hides rail, shows tab bar, and opens sheets from the active tab', async () => {
    const setMobileTab = vi.fn()
    const { rerender } = render(
      <TeacherAppLayout
        {...buildProps({
          teacherUseMobileShellV2: true,
          mobileShellV2Enabled: true,
          isMobileLayout: true,
          mobileTab: 'chat',
          setMobileTab,
        })}
      />,
    )

    const shell = document.querySelector('.app.teacher')
    expect(shell?.getAttribute('data-mobile-shell-v2')).toBe('1')
    expect(shell?.classList.contains('teacher-mobile-shell-v2')).toBe(true)
    expect(screen.queryByTestId('teacher-session-rail')).toBeNull()
    expect(screen.getByTestId('mobile-tab-bar').textContent).toBe('chat')
    expect(screen.queryByTestId('bottom-sheet-历史会话')).toBeNull()

    rerender(
      <TeacherAppLayout
        {...buildProps({
          teacherUseMobileShellV2: true,
          mobileShellV2Enabled: true,
          isMobileLayout: true,
          mobileTab: 'sessions',
          setMobileTab,
        })}
      />,
    )

    expect(screen.getByTestId('bottom-sheet-历史会话')).toBeTruthy()
    expect(screen.getByTestId('session-sidebar')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'close-历史会话' }))
    expect(setMobileTab).toHaveBeenCalledWith('chat')

    rerender(
      <TeacherAppLayout
        {...buildProps({
          teacherUseMobileShellV2: true,
          mobileShellV2Enabled: true,
          isMobileLayout: true,
          mobileTab: 'workbench',
          setMobileTab,
        })}
      />,
    )

    expect(screen.getByTestId('bottom-sheet-工作台')).toBeTruthy()
    expect((await screen.findAllByTestId('teacher-workbench')).length).toBeGreaterThan(0)
  })

  it('opens session rename and archive dialogs from session ids', () => {
    render(
      <TeacherAppLayout
        {...buildProps({
          renameDialogSessionId: 's1',
          archiveDialogSessionId: 's2',
          archiveDialogActionLabel: '归档',
        })}
      />,
    )

    expect(screen.getByTestId('prompt-dialog').textContent).toBe('重命名会话')
    expect(screen.getByTestId('confirm-dialog').textContent).toContain('归档')
  })
})
