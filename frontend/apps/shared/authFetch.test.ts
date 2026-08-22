import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { clearStudentAccessToken } from '../student/src/features/auth/studentAuth';
import { normalizeApiBase, resolveRuntimeApiBase } from './apiBase';
import { installAuthFetchInterceptor } from './authFetch';

type UnauthorizedContext = {
  tokenKey: string;
  response: Response;
};

describe('normalizeApiBase', () => {
  it('rejects javascript: and userinfo', () => {
    expect(normalizeApiBase('javascript:alert(1)')).toBe('');
    expect(normalizeApiBase('https://user:pass@evil.example/api')).toBe('');
    expect(normalizeApiBase("http://localhost:8000/'onclick=alert(1)")).toBe('');
  });

  it('keeps origin and path without a trailing slash', () => {
    expect(normalizeApiBase('http://localhost:8000/')).toBe('http://localhost:8000');
    expect(normalizeApiBase('https://api.example.com/v1/')).toBe('https://api.example.com/v1');
  });
});

describe('resolveRuntimeApiBase', () => {
  it('production ignores user-overridden API base', () => {
    expect(resolveRuntimeApiBase('https://evil.example', true)).toBe(
      resolveRuntimeApiBase(null, true),
    );
    expect(resolveRuntimeApiBase('https://evil.example', true)).not.toBe('https://evil.example');
  });

  it('development accepts a normalized override', () => {
    expect(resolveRuntimeApiBase('https://api.example.com/v1/', false)).toBe(
      'https://api.example.com/v1',
    );
  });
});

describe('installAuthFetchInterceptor', () => {
  const tokenKey = 'teacherAuthAccessToken';
  const apiBase = 'http://localhost:8000';
  const tokenStore = new Map<string, string>();
  let originalFetch: typeof window.fetch;
  let originalLocalStorage: unknown;

  beforeEach(() => {
    originalFetch = window.fetch.bind(window);
    originalLocalStorage = window.localStorage;
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: {
        getItem: (key: string) => tokenStore.get(key) ?? null,
        setItem: (key: string, value: string) => {
          tokenStore.set(key, String(value));
        },
        removeItem: (key: string) => {
          tokenStore.delete(key);
        },
        clear: () => {
          tokenStore.clear();
        },
      },
    });
    tokenStore.clear();
    delete window.__authFetchState;
  });

  afterEach(() => {
    window.fetch = originalFetch;
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: originalLocalStorage,
    });
    tokenStore.clear();
    delete window.__authFetchState;
  });

  it('adds bearer token from localStorage when request has no Authorization header', async () => {
    window.localStorage.setItem(tokenKey, 'token-123');
    const upstreamFetch = vi.fn(
      async (_input: RequestInfo | URL, _init?: RequestInit) => new Response('{}', { status: 200 }),
    );
    window.fetch = upstreamFetch as unknown as typeof window.fetch;

    installAuthFetchInterceptor(tokenKey, { apiBase });
    await window.fetch('/teacher/history/sessions');

    expect(upstreamFetch).toHaveBeenCalledTimes(1);
    const init = upstreamFetch.mock.calls[0]?.[1] as RequestInit | undefined;
    const headers = new Headers(init?.headers);
    expect(headers.get('Authorization')).toBe('Bearer token-123');
  });

  it('adds bearer only for api origin', async () => {
    window.localStorage.setItem(tokenKey, 'token-123');
    const upstreamFetch = vi.fn(
      async (_input: RequestInfo | URL, _init?: RequestInit) => new Response('{}', { status: 200 }),
    );
    window.fetch = upstreamFetch as unknown as typeof window.fetch;

    installAuthFetchInterceptor(tokenKey, { apiBase });
    await window.fetch('http://localhost:8000/teacher/history/sessions');
    await window.fetch('https://evil.example/steal');
    await window.fetch(new Request('https://evil.example/steal'));
    await window.fetch('//evil.example/steal');

    expect(upstreamFetch).toHaveBeenCalledTimes(4);
    const apiHeaders = new Headers(upstreamFetch.mock.calls[0]?.[1]?.headers);
    expect(apiHeaders.get('Authorization')).toBe('Bearer token-123');
    expect(upstreamFetch.mock.calls[1]?.[1]).toBeUndefined();
    expect(upstreamFetch.mock.calls[2]?.[1]).toBeUndefined();
    expect(upstreamFetch.mock.calls[3]?.[1]).toBeUndefined();
  });

  it('runs onUnauthorized callback once for an active token that receives 401', async () => {
    window.localStorage.setItem(tokenKey, 'token-401');
    const upstreamFetch = vi.fn(
      async (_input: RequestInfo | URL, _init?: RequestInit) =>
        new Response('{"detail":"token_expired"}', { status: 401 }),
    );
    window.fetch = upstreamFetch as unknown as typeof window.fetch;

    const onUnauthorized = vi.fn((_: UnauthorizedContext) => {
      window.localStorage.removeItem(tokenKey);
    });

    installAuthFetchInterceptor(tokenKey, { onUnauthorized, apiBase });
    const res = await window.fetch('/teacher/history/sessions');

    expect(res.status).toBe(401);
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
    const firstCall = onUnauthorized.mock.calls[0]?.[0];
    expect(firstCall?.tokenKey).toBe(tokenKey);
    expect(firstCall?.response.status).toBe(401);
    expect(window.localStorage.getItem(tokenKey)).toBeNull();
  });

  it('does not run onUnauthorized when token was already cleared before response handling', async () => {
    window.localStorage.setItem(tokenKey, 'stale-token');
    const upstreamFetch = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => {
      window.localStorage.removeItem(tokenKey);
      return new Response('{"detail":"missing_authorization"}', { status: 401 });
    });
    window.fetch = upstreamFetch as unknown as typeof window.fetch;

    const onUnauthorized = vi.fn();
    installAuthFetchInterceptor(tokenKey, { onUnauthorized, apiBase });
    await window.fetch('/teacher/history/sessions');

    expect(onUnauthorized).not.toHaveBeenCalled();
  });

  it('student 401 clears studentAuthAccessToken only', async () => {
    const studentTokenKey = 'studentAuthAccessToken';
    window.localStorage.setItem(studentTokenKey, 'student-token');
    window.localStorage.setItem('studentMobileShellV2', '1');
    window.localStorage.setItem('studentPendingChatJob:s1', '{}');
    const upstreamFetch = vi.fn(
      async (_input: RequestInfo | URL, _init?: RequestInit) =>
        new Response('{"detail":"token_expired"}', { status: 401 }),
    );
    window.fetch = upstreamFetch as unknown as typeof window.fetch;

    installAuthFetchInterceptor(studentTokenKey, {
      onUnauthorized: () => {
        clearStudentAccessToken();
      },
      apiBase,
    });
    await window.fetch('/student/history/sessions');

    expect(window.localStorage.getItem(studentTokenKey)).toBeNull();
    expect(window.localStorage.getItem('studentMobileShellV2')).toBe('1');
    expect(window.localStorage.getItem('studentPendingChatJob:s1')).toBe('{}');
  });
});
