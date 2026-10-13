import { createRef } from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import StudentMobileShell from './StudentMobileShell';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const buildProps = () => ({
  appRef: createRef<HTMLDivElement>(),
  mobileShellV2Enabled: true,
  verifiedStudent: null,
  sidebarOpen: false,
  homeOpen: true,
  dispatch: vi.fn(),
  openTodayHome: vi.fn(),
  startNewStudentSession: vi.fn(),
  mobileTab: 'learning' as const,
  onMobileTabChange: vi.fn(),
  mobileLearningContent: <div>learning-slot</div>,
  mobileSessionsContent: <div>sessions-slot</div>,
  chatContent: <div>chat-slot</div>,
  sessionDialogs: null,
});

describe('StudentMobileShell', () => {
  it('uses mobile shell v2 root class, student-main on the shell main, and one skip link', () => {
    render(<StudentMobileShell {...buildProps()} />);

    const shell = document.querySelector('.app');
    expect(shell?.className).toContain('student-mobile-shell-v2');
    expect(shell?.getAttribute('data-mobile-shell-v2')).toBe('1');

    const main = document.querySelector('.student-mobile-shell-main');
    expect(main).toBeTruthy();
    expect(main?.getAttribute('id')).toBe('student-main');
    expect(document.querySelectorAll('#student-main')).toHaveLength(1);

    const skips = screen.getAllByRole('link', { name: '跳到主内容' });
    expect(skips).toHaveLength(1);
    expect(skips[0].getAttribute('href')).toBe('#student-main');
    expect(shell?.firstElementChild).toBe(skips[0]);
  });
});
