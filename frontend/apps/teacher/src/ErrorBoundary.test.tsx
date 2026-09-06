import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import ErrorBoundary from './ErrorBoundary';

const Boom = () => {
  throw new Error('teacher-crash');
};

describe('ErrorBoundary', () => {
  const originalConsoleError = console.error;

  beforeEach(() => {
    console.error = vi.fn();
    window.localStorage.clear();
    window.localStorage.setItem('teacherAuthAccessToken', 'teacher-token');
    window.localStorage.setItem('teacherPendingChatJob', '{"job_id":"j1"}');
    window.localStorage.setItem('teacherSessionViewState', '{"title_map":{}}');
    window.localStorage.setItem('teacherMobileShellV2', '1');
    window.localStorage.setItem('teacherSurveyAnalysis', '1');
    window.localStorage.setItem('apiBaseTeacher', 'http://localhost:8000');
  });

  afterEach(() => {
    cleanup();
    console.error = originalConsoleError;
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it('clears auth, pending job, and session view keys but keeps unrelated keys', () => {
    const reload = vi.fn();
    vi.stubGlobal('location', { reload });

    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );

    fireEvent.click(screen.getByRole('button', { name: '清空本地缓存并刷新' }));

    expect(window.localStorage.getItem('teacherAuthAccessToken')).toBeNull();
    expect(window.localStorage.getItem('teacherPendingChatJob')).toBeNull();
    expect(window.localStorage.getItem('teacherSessionViewState')).toBeNull();
    expect(window.localStorage.getItem('teacherMobileShellV2')).toBe('1');
    expect(window.localStorage.getItem('teacherSurveyAnalysis')).toBe('1');
    expect(window.localStorage.getItem('apiBaseTeacher')).toBe('http://localhost:8000');
    expect(reload).toHaveBeenCalledTimes(1);
  });
});
