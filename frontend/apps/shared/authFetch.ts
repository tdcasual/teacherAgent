import { safeLocalStorageGetItem } from './storage';

type AuthFetchState = {
  originalFetch: typeof window.fetch;
  tokenKeys: Set<string>;
};

declare global {
  interface Window {
    __authFetchState?: AuthFetchState;
  }
}

const firstToken = (keys: Set<string>): string => {
  for (const key of keys) {
    const token = String(safeLocalStorageGetItem(key) || '').trim();
    if (token) return token;
  }
  return '';
};

export const installAuthFetchInterceptor = (tokenKey: string) => {
  if (typeof window === 'undefined') return;
  const key = String(tokenKey || '').trim();
  if (!key) return;

  const existing = window.__authFetchState;
  if (existing) {
    existing.tokenKeys.add(key);
    return;
  }

  const state: AuthFetchState = {
    originalFetch: window.fetch.bind(window),
    tokenKeys: new Set<string>([key]),
  };
  window.__authFetchState = state;

  window.fetch = (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const token = firstToken(state.tokenKeys);
    if (!token) return state.originalFetch(input, init);

    const headers = new Headers(init?.headers);
    if (!headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${token}`);
    }
    return state.originalFetch(input, { ...(init || {}), headers });
  };
};
