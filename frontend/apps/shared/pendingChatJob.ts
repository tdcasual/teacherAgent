export const PENDING_CHAT_MAX_AGE_MS = 15 * 60 * 1000;

export type PendingChatJob = {
  job_id: string;
  request_id: string;
  placeholder_id: string;
  user_text: string;
  session_id: string;
  created_at: number;
  lane_id?: string;
};

const isExpired = (createdAt: number, nowMs: number): boolean =>
  nowMs - createdAt > PENDING_CHAT_MAX_AGE_MS;

const parseJsonObject = (raw: string | null): Record<string, unknown> | null => {
  if (!raw) return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;
    return parsed as Record<string, unknown>;
  } catch {
    return null;
  }
};

export const parsePendingChatJob = (
  raw: string | null,
  nowMs: number = Date.now(),
): PendingChatJob | null => {
  const record = parseJsonObject(raw);
  if (!record) return null;
  const jobId = String(record.job_id || '').trim();
  const requestId = String(record.request_id || '').trim();
  const placeholderId = String(record.placeholder_id || '').trim();
  const userText = String(record.user_text || '').trim();
  const sessionId = String(record.session_id || '').trim();
  const createdAt = Number(record.created_at);
  if (!jobId || !requestId || !placeholderId || !userText || !sessionId) return null;
  if (!Number.isFinite(createdAt)) return null;
  if (isExpired(createdAt, nowMs)) return null;
  const laneId = String(record.lane_id || '').trim();
  return {
    job_id: jobId,
    request_id: requestId,
    placeholder_id: placeholderId,
    user_text: userText,
    session_id: sessionId,
    created_at: createdAt,
    ...(laneId ? { lane_id: laneId } : {}),
  };
};

const normalizeStudentPendingChatJob = (value: unknown, nowMs: number): PendingChatJob | null => {
  if (!value || typeof value !== 'object') return null;
  const candidate = value as Partial<PendingChatJob>;
  const jobId = String(candidate.job_id || '').trim();
  if (!jobId) return null;
  const createdAt = Number(candidate.created_at || 0);
  if (!Number.isFinite(createdAt) || createdAt <= 0) return null;
  if (isExpired(createdAt, nowMs)) return null;

  const requestId = String(candidate.request_id || '').trim();
  const placeholderId = String(candidate.placeholder_id || '').trim() || `asst_recover_${jobId}`;
  const userText = typeof candidate.user_text === 'string' ? candidate.user_text : '';
  const sessionId = String(candidate.session_id || '').trim();

  return {
    job_id: jobId,
    request_id: requestId,
    placeholder_id: placeholderId,
    user_text: userText,
    session_id: sessionId,
    created_at: createdAt,
  };
};

export const parsePendingChatJobFromStorage = (
  raw: string | null,
  nowMs: number = Date.now(),
): PendingChatJob | null => {
  if (!raw) return null;
  try {
    return normalizeStudentPendingChatJob(JSON.parse(raw), nowMs);
  } catch {
    return null;
  }
};
