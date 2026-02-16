import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { installAuthFetchInterceptor } from './authFetch';

type UnauthorizedContext = {
  tokenKey: string;
  response: Response;
};

describe('installAuthFetchInterceptor', () => {
  const tokenKey = 'teacherAuthAccessToken';
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

    installAuthFetchInterceptor(tokenKey);
    await window.fetch('/teacher/history/sessions');

    expect(upstreamFetch).toHaveBeenCalledTimes(1);
    const init = upstreamFetch.mock.calls[0]?.[1] as RequestInit | undefined;
    const headers = new Headers(init?.headers);
    expect(headers.get('Authorization')).toBe('Bearer token-123');
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

    installAuthFetchInterceptor(tokenKey, { onUnauthorized });
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
    installAuthFetchInterceptor(tokenKey, { onUnauthorized });
    await window.fetch('/teacher/history/sessions');

    expect(onUnauthorized).not.toHaveBeenCalled();
  });
});
