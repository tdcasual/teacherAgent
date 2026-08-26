const CONTROL_CHARS_RE = /[\u0000-\u001f\u007f]/;
const DANGEROUS_CHARS_RE = /["'`<>]/;
const FALLBACK_API_BASE = 'http://localhost:8000';

export const normalizeApiBase = (base: string): string => {
  const raw = String(base || '').trim();
  if (!raw) return '';
  if (CONTROL_CHARS_RE.test(raw) || DANGEROUS_CHARS_RE.test(raw)) return '';
  let parsed: URL;
  try {
    parsed = new URL(raw);
  } catch {
    return '';
  }
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return '';
  if (parsed.username || parsed.password) return '';
  const pathname = parsed.pathname.replace(/\/+$/, '');
  return `${parsed.origin}${pathname}`;
};

export const envApiBase = (): string =>
  normalizeApiBase(String(import.meta.env.VITE_API_URL || '')) || FALLBACK_API_BASE;

export const resolveRuntimeApiBase = (
  override?: string | null,
  production: boolean = Boolean(import.meta.env.PROD),
): string => {
  const pinned = envApiBase();
  if (production) return pinned;
  return normalizeApiBase(String(override || '')) || pinned;
};
