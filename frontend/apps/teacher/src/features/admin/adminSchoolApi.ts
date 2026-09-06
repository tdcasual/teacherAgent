import { readTeacherAccessToken } from '../auth/teacherAuth';

export const toText = (value: unknown): string => String(value ?? '').trim();

export function adminTokenHeaders(): HeadersInit {
  const token = readTeacherAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function adminJsonHeaders(): HeadersInit {
  return {
    'Content-Type': 'application/json',
    ...adminTokenHeaders(),
  };
}

export function errorDetail(
  data: { detail?: string; error?: string; message?: string },
  fallback: string,
): string {
  return toText(data.detail || data.error) || data.message || fallback;
}
