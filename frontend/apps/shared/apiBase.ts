const CONTROL_CHARS_RE = /[\u0000-\u001f\u007f]/;
const DANGEROUS_CHARS_RE = /["'`<>]/;

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
