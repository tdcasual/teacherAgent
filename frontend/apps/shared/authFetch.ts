import { normalizeApiBase, resolveRuntimeApiBase } from './apiBase';
import { safeLocalStorageGetItem } from './storage';

type AuthFetchUnauthorizedContext = {
  tokenKey: string;
  response: Response;
};

type AuthFetchUnauthorizedHandler = (context: AuthFetchUnauthorizedContext) => void | Promise<void>;

type AuthFetchOptions = {
  onUnauthorized?: AuthFetchUnauthorizedHandler;
  apiBase?: string;
};

type AuthFetchState = {
  originalFetch: typeof window.fetch;
  tokenHandlers: Map<string, AuthFetchUnauthorizedHandler | undefined>;
  apiBase: string;
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

const requestUrlOf = (input: RequestInfo | URL): string => {
  if (typeof input === 'string') return input;
  if (typeof URL !== 'undefined' && input instanceof URL) return input.href;
  if (typeof Request !== 'undefined' && input instanceof Request) return input.url;
  return String(input);
};

const isApiOriginRequest = (input: RequestInfo | URL, apiBase: string): boolean => {
  const raw = requestUrlOf(input).trim();
  if (!raw || raw.startsWith('//')) return false;
  let parsed: URL;
  try {
    parsed = new URL(raw);
  } catch {
    // Relative URLs are same-origin API calls.
    return true;
  }
  const allowed = normalizeApiBase(apiBase);
  if (!allowed) return false;
  try {
    return parsed.origin === new URL(allowed).origin;
  } catch {
    return false;
  }
};

const applyInstallOptions = (state: AuthFetchState, key: string, options?: AuthFetchOptions) => {
  if (!options || 'onUnauthorized' in options) {
    state.tokenHandlers.set(key, options?.onUnauthorized);
  } else if (!state.tokenHandlers.has(key)) {
    state.tokenHandlers.set(key, undefined);
  }
  if (options && 'apiBase' in options) {
    state.apiBase = String(options.apiBase || '');
  }
};

export const installAuthFetchInterceptor = (tokenKey: string, options?: AuthFetchOptions) => {
  if (typeof window === 'undefined') return;
  const key = String(tokenKey || '').trim();
  if (!key) return;

  const existing = window.__authFetchState;
  if (existing) {
    applyInstallOptions(existing, key, options);
    return;
  }

  const state: AuthFetchState = {
    originalFetch: window.fetch.bind(window),
    tokenHandlers: new Map<string, AuthFetchUnauthorizedHandler | undefined>(),
    apiBase: String(options?.apiBase || ''),
  };
  applyInstallOptions(state, key, options);
  window.__authFetchState = state;

  window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const effectiveApiBase = resolveRuntimeApiBase(state.apiBase);
    if (!isApiOriginRequest(input, effectiveApiBase)) {
      return state.originalFetch(input, init);
    }

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
        await authState.onUnauthorized({
          tokenKey: authState.tokenKey,
          response: response.clone(),
        });
      } catch {
        // keep request flow unaffected when unauthorized callback fails
      }
    }
    return response;
  };
};
