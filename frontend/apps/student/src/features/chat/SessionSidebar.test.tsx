import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import SessionSidebar from './SessionSidebar';

vi.mock('./SessionSidebarDialogs', () => ({ default: () => null }));
vi.mock('./SessionSidebarHistorySection', () => ({ default: () => <div>history</div> }));
vi.mock('./SessionSidebarLearningSection', () => ({ default: () => <div>learning</div> }));

afterEach(() => {
  cleanup();
});

const baseProps = {
  dispatch: vi.fn(),
  verifiedStudent: { student_id: 'S1', student_name: 'A' },
  historyLoading: false,
  historyError: '',
  historyHasMore: false,
  refreshSessions: vi.fn(),
  showArchivedSessions: false,
  historyQuery: '',
  visibleSessionCount: 0,
  groupedSessions: [],
  deletedSessionIds: [],
  activeSessionId: '',
  onSelectSession: vi.fn(),
  getSessionTitle: () => '',
  openSessionMenuId: '',
  toggleSessionMenu: vi.fn(),
  handleSessionMenuTriggerKeyDown: vi.fn(),
  handleSessionMenuKeyDown: vi.fn(),
  setSessionMenuTriggerRef: vi.fn(),
  setSessionMenuRef: vi.fn(),
} as const;

describe('student SessionSidebar overlay', () => {
  it('mounts overlay only when open', () => {
    const { rerender } = render(<SessionSidebar {...(baseProps as any)} sidebarOpen={false} />);
    expect(screen.queryByRole('button', { name: '关闭会话侧栏' })).toBeNull();
    rerender(<SessionSidebar {...(baseProps as any)} sidebarOpen />);
    expect(screen.getByRole('button', { name: '关闭会话侧栏' })).toBeTruthy();
  });
});
