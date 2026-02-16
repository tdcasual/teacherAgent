import { safeLocalStorageGetItem } from './storage';

type AuthFetchUnauthorizedContext = {
  tokenKey: string;
  response: Response;
};

type AuthFetchUnauthorizedHandler = (
  context: AuthFetchUnauthorizedContext,
) => void | Promise<void>;

type AuthFetchState = {
  originalFetch: typeof window.fetch;
  tokenHandlers: Map<string, AuthFetchUnauthorizedHandler | undefined>;
};

declare global {
  interface Window {
    __authFetchState?: AuthFetchState;
  }
}

const firstToken = (
  handlers: Map<string, AuthFetchUnauthorizedHandler | undefined>,
): { tokenKey: string; token: string; onUnauthorized?: AuthFetchUnauthorizedHandler } | null => {
  for (const [key, onUnauthorized] of handlers.entries()) {
    const token = String(safeLocalStorageGetItem(key) || '').trim();
    if (token) return { tokenKey: key, token, onUnauthorized };
  }
  return null;
};

export const installAuthFetchInterceptor = (
  tokenKey: string,
  options?: { onUnauthorized?: AuthFetchUnauthorizedHandler },
) => {
  if (typeof window === 'undefined') return;
  const key = String(tokenKey || '').trim();
  if (!key) return;

  const existing = window.__authFetchState;
  if (existing) {
    existing.tokenHandlers.set(key, options?.onUnauthorized);
    return;
  }

  const state: AuthFetchState = {
    originalFetch: window.fetch.bind(window),
    tokenHandlers: new Map<string, AuthFetchUnauthorizedHandler | undefined>([
      [key, options?.onUnauthorized],
    ]),
  };
  window.__authFetchState = state;

  window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const authState = firstToken(state.tokenHandlers);
    if (!authState) return state.originalFetch(input, init);

    const headers = new Headers(init?.headers);
    if (!headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${authState.token}`);
    }

    const response = await state.originalFetch(input, { ...(init || {}), headers });
    if (response.status !== 401 || !authState.onUnauthorized) {
      return response;
    }

    // Only treat as auth-expired when the same token is still active in storage.
    // This avoids duplicate callbacks from concurrent requests after the first clear.
    const activeToken = String(safeLocalStorageGetItem(authState.tokenKey) || '').trim();
    if (activeToken && activeToken === authState.token) {
      try {
        await authState.onUnauthorized({ tokenKey: authState.tokenKey, response: response.clone() });
      } catch {
        // keep request flow unaffected when unauthorized callback fails
      }
    }
    return response;
  };
};
