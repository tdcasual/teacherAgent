import { useEffect, useState, type Dispatch, type SetStateAction } from 'react';
import { parsePendingChatJob } from '../../../../shared/pendingChatJob';
import type { Message, PendingChatJob, PendingToolRun } from '../../appTypes';
import {
  safeLocalStorageGetItem,
  safeLocalStorageRemoveItem,
  safeLocalStorageSetItem,
} from '../../utils/storage';
import { withPendingChatOverlay } from './pendingOverlay';

export const TEACHER_PENDING_CHAT_KEY = 'teacherPendingChatJob';

type UseTeacherPendingChatJobParams = {
  activeSessionId: string;
  setActiveSessionId: (value: string | ((prev: string) => string)) => void;
  setLocalDraftSessionIds: (value: string[] | ((prev: string[]) => string[])) => void;
  setMessages: Dispatch<SetStateAction<Message[]>>;
  setPendingStreamStage: Dispatch<SetStateAction<string>>;
  setPendingToolRuns: Dispatch<SetStateAction<PendingToolRun[]>>;
};

export function useTeacherPendingChatJob(params: UseTeacherPendingChatJobParams) {
  const {
    activeSessionId,
    setActiveSessionId,
    setLocalDraftSessionIds,
    setMessages,
    setPendingStreamStage,
    setPendingToolRuns,
  } = params;
  const [pendingChatJob, setPendingChatJob] = useState<PendingChatJob | null>(() =>
    parsePendingChatJob(safeLocalStorageGetItem(TEACHER_PENDING_CHAT_KEY)),
  );

  useEffect(() => {
    const sid = String(pendingChatJob?.session_id || '').trim();
    if (!sid || sid === 'main') return;
    setLocalDraftSessionIds((prev) => (prev.includes(sid) ? prev : [sid, ...prev]));
  }, [pendingChatJob?.session_id, setLocalDraftSessionIds]);

  useEffect(() => {
    if (pendingChatJob)
      safeLocalStorageSetItem(TEACHER_PENDING_CHAT_KEY, JSON.stringify(pendingChatJob));
    else safeLocalStorageRemoveItem(TEACHER_PENDING_CHAT_KEY);
  }, [pendingChatJob]);

  useEffect(() => {
    if (pendingChatJob?.job_id) return;
    setPendingStreamStage('');
    setPendingToolRuns([]);
  }, [pendingChatJob?.job_id, setPendingStreamStage, setPendingToolRuns]);

  useEffect(() => {
    if (!pendingChatJob?.job_id) return;
    if (!activeSessionId || pendingChatJob.session_id !== activeSessionId) return;
    setMessages((prev) => withPendingChatOverlay(prev, pendingChatJob, activeSessionId));
  }, [
    activeSessionId,
    pendingChatJob,
    pendingChatJob?.created_at,
    pendingChatJob?.job_id,
    pendingChatJob?.placeholder_id,
    pendingChatJob?.session_id,
    pendingChatJob?.user_text,
    setMessages,
  ]);

  useEffect(() => {
    if (!pendingChatJob?.job_id) return;
    if (pendingChatJob.session_id && pendingChatJob.session_id !== activeSessionId) {
      setActiveSessionId(pendingChatJob.session_id);
    }
    // Run only on mount to recover the original pending session once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    pendingChatJob,
    setPendingChatJob,
    pendingChatKey: TEACHER_PENDING_CHAT_KEY,
  };
}
