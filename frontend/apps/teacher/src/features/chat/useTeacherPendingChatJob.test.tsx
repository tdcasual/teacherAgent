import { act, renderHook } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { PENDING_CHAT_MAX_AGE_MS } from '../../../../shared/pendingChatJob';
import type { Message, PendingChatJob, PendingToolRun } from '../../appTypes';
import { TEACHER_PENDING_CHAT_KEY, useTeacherPendingChatJob } from './useTeacherPendingChatJob';

const freshJob = (): PendingChatJob => ({
  job_id: 'job_1',
  request_id: 'req_1',
  placeholder_id: 'asst_1',
  user_text: '帮我出一份作业',
  session_id: 'sess_pending',
  created_at: Date.now(),
  lane_id: 'lane_a',
});

const usePendingHarness = (activeSessionId: string) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [pendingStreamStage, setPendingStreamStage] = useState('routing');
  const [pendingToolRuns, setPendingToolRuns] = useState<PendingToolRun[]>([
    { key: 'tool-1', name: 'search', status: 'running' },
  ]);
  const [localDraftSessionIds, setLocalDraftSessionIds] = useState<string[]>([]);
  const [sessionId, setActiveSessionId] = useState(activeSessionId);
  const pending = useTeacherPendingChatJob({
    activeSessionId: sessionId,
    setActiveSessionId,
    setLocalDraftSessionIds,
    setMessages,
    setPendingStreamStage,
    setPendingToolRuns,
  });
  return {
    messages,
    pendingStreamStage,
    pendingToolRuns,
    localDraftSessionIds,
    sessionId,
    setActiveSessionId,
    ...pending,
  };
};

describe('useTeacherPendingChatJob', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('restores a fresh teacher job from storage via the shared parser', () => {
    const job = freshJob();
    localStorage.setItem(TEACHER_PENDING_CHAT_KEY, JSON.stringify(job));

    const { result } = renderHook(() => usePendingHarness('sess_pending'));

    expect(result.current.pendingChatKey).toBe('teacherPendingChatJob');
    expect(result.current.pendingChatJob).toEqual(job);
  });

  it('discards an expired teacher job using the shared 15 minute TTL', () => {
    localStorage.setItem(
      TEACHER_PENDING_CHAT_KEY,
      JSON.stringify({
        ...freshJob(),
        created_at: Date.now() - PENDING_CHAT_MAX_AGE_MS - 1,
      }),
    );

    const { result } = renderHook(() => usePendingHarness('sess_pending'));

    expect(result.current.pendingChatJob).toBeNull();
  });

  it('persists a pending job and removes storage when cleared', () => {
    const job = freshJob();
    const { result } = renderHook(() => usePendingHarness('main'));

    act(() => {
      result.current.setPendingChatJob(job);
    });
    expect(JSON.parse(localStorage.getItem(TEACHER_PENDING_CHAT_KEY) || 'null')).toEqual(job);

    act(() => {
      result.current.setPendingChatJob(null);
    });
    expect(localStorage.getItem(TEACHER_PENDING_CHAT_KEY)).toBeNull();
  });

  it('overlays the pending user and placeholder bubbles for the matching session', () => {
    const job = freshJob();
    localStorage.setItem(TEACHER_PENDING_CHAT_KEY, JSON.stringify(job));

    const { result } = renderHook(() => usePendingHarness('sess_pending'));

    expect(
      result.current.messages.some((msg) => msg.role === 'user' && msg.content === job.user_text),
    ).toBe(true);
    expect(
      result.current.messages.some(
        (msg) => msg.id === job.placeholder_id && msg.content === '正在生成…',
      ),
    ).toBe(true);
  });

  it('recovers the pending session on mount and records it as a local draft', () => {
    localStorage.setItem(TEACHER_PENDING_CHAT_KEY, JSON.stringify(freshJob()));

    const { result } = renderHook(() => usePendingHarness('main'));

    expect(result.current.sessionId).toBe('sess_pending');
    expect(result.current.localDraftSessionIds).toContain('sess_pending');
  });

  it('does not record the main session as a local draft', () => {
    localStorage.setItem(
      TEACHER_PENDING_CHAT_KEY,
      JSON.stringify({
        ...freshJob(),
        session_id: 'main',
      }),
    );

    const { result } = renderHook(() => usePendingHarness('main'));

    expect(result.current.localDraftSessionIds).toEqual([]);
  });

  it('clears stream stage and tool runs once the pending job is gone', () => {
    localStorage.setItem(TEACHER_PENDING_CHAT_KEY, JSON.stringify(freshJob()));
    const { result } = renderHook(() => usePendingHarness('sess_pending'));

    act(() => {
      result.current.setPendingChatJob(null);
    });

    expect(result.current.pendingStreamStage).toBe('');
    expect(result.current.pendingToolRuns).toEqual([]);
  });
});
