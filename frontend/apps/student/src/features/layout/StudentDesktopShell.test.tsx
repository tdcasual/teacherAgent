import { createRef } from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import StudentDesktopShell from './StudentDesktopShell';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const buildProps = () => ({
  appRef: createRef<HTMLDivElement>(),
  mobileShellV2Enabled: false,
  verifiedStudent: null,
  sidebarOpen: false,
  homeOpen: true,
  assignmentHistoryOpen: false,
  submitAssignmentId: '',
  dispatch: vi.fn(),
  openTodayHome: vi.fn(),
  startNewStudentSession: vi.fn(),
  sidebar: <div>sidebar-slot</div>,
  learningContent: <div>learning-slot</div>,
  chatContent: <div>chat-slot</div>,
});

describe('StudentDesktopShell', () => {
  it('keeps one skip link and uses StudentLayout student-main', () => {
    render(<StudentDesktopShell {...buildProps()} />);

    const shell = document.querySelector('.app');
    expect(shell?.className).not.toContain('student-mobile-shell-v2');
    expect(document.querySelector('.student-mobile-shell-main')).toBeNull();

    const skips = screen.getAllByRole('link', { name: '跳到主内容' });
    expect(skips).toHaveLength(1);
    expect(skips[0].getAttribute('href')).toBe('#student-main');
    expect(shell?.firstElementChild).toBe(skips[0]);

    const main = document.querySelector('#student-main');
    expect(main).toBeTruthy();
    expect(document.querySelectorAll('#student-main')).toHaveLength(1);
    expect(main?.textContent).toContain('learning-slot');
  });
});
