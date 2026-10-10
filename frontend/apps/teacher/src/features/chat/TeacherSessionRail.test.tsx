import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import TeacherSessionRail from './TeacherSessionRail';

vi.mock('./SessionSidebar', () => ({
  default: () => <div>session-sidebar</div>,
}));

afterEach(() => {
  cleanup();
});

const railProps = {
  skillsOpen: false,
  setSessionSidebarOpen: vi.fn(),
  setSkillsOpen: vi.fn(),
  setActiveSessionId: vi.fn(),
  setSessionCursor: vi.fn(),
  setSessionHasMore: vi.fn(),
  setSessionError: vi.fn(),
  setOpenSessionMenuId: vi.fn(),
  closeSessionSidebarOnMobile: vi.fn(),
} as const;

describe('TeacherSessionRail overlay', () => {
  it('hides_overlay_button_when_closed', () => {
    render(
      <TeacherSessionRail
        {...railProps}
        sessionSidebarOpen={false}
        skillsOpen={false}
      />,
    );
    expect(screen.queryByRole('button', { name: '关闭侧边栏' })).toBeNull();
  });

  it('shows overlay button when open', () => {
    render(
      <TeacherSessionRail
        {...railProps}
        sessionSidebarOpen
        skillsOpen={false}
      />,
    );
    expect(screen.getByRole('button', { name: '关闭侧边栏' })).toBeTruthy();
  });
});
