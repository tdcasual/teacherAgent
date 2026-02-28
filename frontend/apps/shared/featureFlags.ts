export const readFeatureFlag = (
  key: string,
  fallback: boolean,
  source: Record<string, string | undefined>,
): boolean => {
  const raw = source[key];
  if (raw == null) return fallback;
  const normalized = String(raw).trim().toLowerCase();
  return normalized === '1' || normalized === 'true';
};
