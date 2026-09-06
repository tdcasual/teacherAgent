import { act, renderHook } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useTeacherMobileShell } from './useTeacherMobileShell';

const DESKTOP_BREAKPOINT = 900;

const stubMatchMedia = (matches: boolean) => {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: (query: string) => ({
      matches,
      media: query,
      onchange: null,
      addListener: () => undefined,
      removeListener: () => undefined,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      dispatchEvent: () => false,
    }),
  });
};

const setViewportWidth = (width: number) => {
  Object.defineProperty(window, 'innerWidth', { configurable: true, writable: true, value: width });
  stubMatchMedia(width <= DESKTOP_BREAKPOINT);
};

const useMobileHarness = () => {
  const [sessionSidebarOpen, setSessionSidebarOpen] = useState(true);
  const [skillsOpen, setSkillsOpen] = useState(true);
  const [activeSessionId, setActiveSessionId] = useState('main');
  const [sessionCursor, setSessionCursor] = useState(7);
  const [sessionHasMore, setSessionHasMore] = useState(true);
  const [sessionError, setSessionError] = useState('old');
  const [openSessionMenuId, setOpenSessionMenuId] = useState('menu-1');
  const shell = useTeacherMobileShell({
    sessionSidebarOpen,
    skillsOpen,
    setSessionSidebarOpen,
    setSkillsOpen,
    setActiveSessionId,
    setSessionCursor,
    setSessionHasMore,
    setSessionError,
    setOpenSessionMenuId,
  });
  return {
    sessionSidebarOpen,
    skillsOpen,
    activeSessionId,
    sessionCursor,
    sessionHasMore,
    sessionError,
    openSessionMenuId,
    ...shell,
  };
};

describe('useTeacherMobileShell', () => {
  beforeEach(() => {
    localStorage.clear();
    setViewportWidth(1280);
  });

  afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it('keeps the desktop shell when the viewport is above the breakpoint', () => {
    const { result } = renderHook(() => useMobileHarness());

    expect(result.current.isMobileLayout).toBe(false);
    expect(result.current.teacherUseMobileShellV2).toBe(false);
    expect(result.current.mobileShellV2Enabled).toBe(true);
    expect(result.current.mobileTab).toBe('chat');
  });

  it('enables the mobile shell on a narrow viewport when the flag is on', () => {
    setViewportWidth(390);
    const { result } = renderHook(() => useMobileHarness());

    expect(result.current.isMobileLayout).toBe(true);
    expect(result.current.teacherUseMobileShellV2).toBe(true);
  });

  it('honors teacherMobileShellV2 localStorage override', () => {
    localStorage.setItem('teacherMobileShellV2', '0');
    setViewportWidth(390);
    const { result } = renderHook(() => useMobileHarness());

    expect(result.current.mobileShellV2Enabled).toBe(false);
    expect(result.current.teacherUseMobileShellV2).toBe(false);
  });

  it('ignores invalid mobile tabs and accepts supported ones', () => {
    setViewportWidth(390);
    const { result } = renderHook(() => useMobileHarness());

    act(() => {
      result.current.handleTeacherMobileTabChange('learning');
    });
    expect(result.current.mobileTab).toBe('chat');

    act(() => {
      result.current.handleTeacherMobileTabChange('sessions');
    });
    expect(result.current.mobileTab).toBe('sessions');
    expect(result.current.sessionSidebarOpen).toBe(true);
    expect(result.current.skillsOpen).toBe(false);
  });

  it('selecting a session from the sheet switches back to chat', () => {
    setViewportWidth(390);
    const { result } = renderHook(() => useMobileHarness());

    act(() => {
      result.current.handleTeacherMobileTabChange('sessions');
    });
    act(() => {
      result.current.handleSelectSessionFromSheet('sess_alpha');
    });

    expect(result.current.activeSessionId).toBe('sess_alpha');
    expect(result.current.sessionCursor).toBe(-1);
    expect(result.current.sessionHasMore).toBe(false);
    expect(result.current.sessionError).toBe('');
    expect(result.current.openSessionMenuId).toBe('');
    expect(result.current.mobileTab).toBe('chat');
  });

  it('toggles mobile tabs from the topbar and falls back to desktop panel toggles', () => {
    setViewportWidth(390);
    const mobile = renderHook(() => useMobileHarness());

    act(() => {
      mobile.result.current.handleTopbarSessionToggle();
    });
    expect(mobile.result.current.mobileTab).toBe('sessions');
    act(() => {
      mobile.result.current.handleTopbarSessionToggle();
    });
    expect(mobile.result.current.mobileTab).toBe('chat');

    act(() => {
      mobile.result.current.handleTopbarWorkbenchToggle();
    });
    expect(mobile.result.current.mobileTab).toBe('workbench');
    expect(mobile.result.current.skillsOpen).toBe(true);
    expect(mobile.result.current.sessionSidebarOpen).toBe(false);

    setViewportWidth(1280);
    const desktop = renderHook(() => useMobileHarness());
    expect(desktop.result.current.teacherUseMobileShellV2).toBe(false);

    act(() => {
      desktop.result.current.handleTopbarSessionToggle();
    });
    expect(desktop.result.current.sessionSidebarOpen).toBe(false);

    act(() => {
      desktop.result.current.handleTopbarWorkbenchToggle();
    });
    expect(desktop.result.current.skillsOpen).toBe(false);
  });
});
