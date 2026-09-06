import { useEffect, type Dispatch, type MutableRefObject, type SetStateAction } from 'react';
import { CHAT_STREAM_EVENT_VERSION, parseChatStreamEnvelope } from './streamEventProtocol';
import {
  appendExecutionTimelineEntry,
  buildExecutionTimelineEntry,
  resolveWorkflowHint,
} from './useTeacherChatApiHelpers';
import type {
  ExecutionTimelineEntry,
  Message,
  PendingChatJob,
  PendingToolRun,
  Skill,
} from '../../appTypes';
import {
  applyTeacherChatProcessingHints,
  applyTeacherChatQueuedHints,
  createTeacherChatPendingJobHandlers,
  fetchTeacherChatJobStatus,
  startTeacherChatStatusPolling,
} from './useTeacherChatStatus';

export type UseTeacherChatStreamParams = {
  apiBase: string;
  authToken: string;
  pendingChatJob: PendingChatJob | null;
  pendingChatJobRef: MutableRefObject<PendingChatJob | null>;
  activeSessionId: string;
  skillList: Skill[];
  setMessages: Dispatch<SetStateAction<Message[]>>;
  setPendingChatJob: Dispatch<SetStateAction<PendingChatJob | null>>;
  setChatQueueHint: Dispatch<SetStateAction<string>>;
  setPendingStreamStage: Dispatch<SetStateAction<string>>;
  setPendingToolRuns: Dispatch<SetStateAction<PendingToolRun[]>>;
  setExecutionTimeline: Dispatch<SetStateAction<ExecutionTimelineEntry[]>>;
  setSending: Dispatch<SetStateAction<boolean>>;
  setComposerWarning: Dispatch<SetStateAction<string>>;
  refreshTeacherSessions: () => Promise<void> | void;
  setToolConfirm: Dispatch<
    SetStateAction<{ confirm_id: string; tool: string; preview: string } | null>
  >;
};

export function useTeacherChatStream(params: UseTeacherChatStreamParams) {
  const {
    apiBase,
    authToken,
    pendingChatJob,
    pendingChatJobRef,
    activeSessionId,
    skillList,
    setMessages,
    setPendingChatJob,
    setChatQueueHint,
    setPendingStreamStage,
    setPendingToolRuns,
    setExecutionTimeline,
    setSending,
    setComposerWarning,
    refreshTeacherSessions,
    setToolConfirm,
  } = params;

  useEffect(() => {
    if (!authToken) return;
    if (!pendingChatJob?.job_id) return;
    let stopped = false;
    let pollCleanup: (() => void) | null = null;
    let pollStarted = false;
    const controller = new AbortController();
    const { setPlaceholderContent, finishSuccess, finishFailure } =
      createTeacherChatPendingJobHandlers({
        pendingChatJob,
        pendingChatJobRef,
        activeSessionId,
        setMessages,
        setPendingChatJob,
        setChatQueueHint,
        setPendingStreamStage,
        setPendingToolRuns,
        setSending,
        refreshTeacherSessions,
      });
    const startFallbackPolling = () => {
      if (pollStarted || stopped) return;
      pollStarted = true;
      pollCleanup = startTeacherChatStatusPolling({
        apiBase,
        pendingChatJob,
        activeSessionId,
        finishSuccess,
        finishFailure,
        setPlaceholderContent,
        setChatQueueHint,
        setPendingStreamStage,
        setExecutionTimeline,
      });
    };
    const streamSleep = async (ms: number) =>
      new Promise<void>((resolve) => window.setTimeout(resolve, ms));
    const runStream = async () => {
      let cursor = 0;
      let reconnectAttempts = 0;
      let assistantText = '';
      let toolCounter = 0;
      const toolStates: PendingToolRun[] = [];
      let assistantRenderTimer: number | null = null;
      let assistantRenderScheduled = false;
      const clearAssistantRenderTimer = () => {
        if (assistantRenderTimer !== null) {
          window.clearTimeout(assistantRenderTimer);
          assistantRenderTimer = null;
        }
        assistantRenderScheduled = false;
      };
      const flushAssistantPlaceholder = () => {
        assistantRenderTimer = null;
        assistantRenderScheduled = false;
        setPlaceholderContent(assistantText || '正在生成…');
      };
      const scheduleAssistantPlaceholder = () => {
        if (assistantRenderScheduled) return;
        assistantRenderScheduled = true;
        assistantRenderTimer = window.setTimeout(() => {
          flushAssistantPlaceholder();
        }, 40);
      };
      const renderStreamingPlaceholder = () => {
        clearAssistantRenderTimer();
        setPendingToolRuns([...toolStates]);
        setPlaceholderContent(assistantText || '正在生成…');
      };
      const applyStreamEvent = (
        eventType: string,
        payload: Record<string, unknown>,
        eventId: number,
      ) => {
        if (eventId > cursor) cursor = eventId;
        appendExecutionTimelineEntry(
          setExecutionTimeline,
          buildExecutionTimelineEntry(eventType, payload, skillList),
        );
        if (eventType === 'job.queued') {
          const lanePos = Number(payload.lane_queue_position || 0);
          const laneSize = Number(payload.lane_queue_size || 0);
          applyTeacherChatQueuedHints(lanePos, laneSize, setChatQueueHint, setPendingStreamStage);
          return;
        }
        if (eventType === 'job.processing') {
          applyTeacherChatProcessingHints(setChatQueueHint, setPendingStreamStage);
          return;
        }
        if (eventType === 'workflow.resolved') {
          const workflowHint = resolveWorkflowHint(
            {
              requested_skill_id: String(payload.requested_skill_id || ''),
              effective_skill_id: String(payload.effective_skill_id || ''),
              reason: String(payload.reason || ''),
            },
            skillList,
          );
          if (workflowHint) setComposerWarning(workflowHint);
          return;
        }
        if (eventType === 'tool.confirm_required') {
          const confirmId = String(payload.confirm_id || '').trim();
          if (confirmId) {
            setToolConfirm({
              confirm_id: confirmId,
              tool: String(payload.tool || '').trim() || 'tool',
              preview: String(payload.preview || '').trim(),
            });
            setPendingStreamStage('等待确认写操作…');
          }
          renderStreamingPlaceholder();
          return;
        }
        if (eventType === 'tool.start') {
          toolCounter += 1;
          const toolName = String(payload.tool_name || '').trim() || 'tool';
          const callId = String(payload.tool_call_id || '').trim();
          const key = callId || `${toolName}#${toolCounter}`;
          toolStates.push({ key, name: toolName, status: 'running' });
          renderStreamingPlaceholder();
          return;
        }
        if (eventType === 'tool.finish') {
          const toolName = String(payload.tool_name || '').trim() || 'tool';
          const callId = String(payload.tool_call_id || '').trim();
          const byCallId = callId ? toolStates.findIndex((item) => item.key === callId) : -1;
          const byName = toolStates.findIndex(
            (item) => item.status === 'running' && item.name === toolName,
          );
          const idx = byCallId >= 0 ? byCallId : byName;
          const ok = Boolean(payload.ok);
          const durationMs = Number(payload.duration_ms || 0);
          const error = String(payload.error || '').trim();
          if (idx >= 0) {
            toolStates[idx] = {
              ...toolStates[idx],
              status: ok ? 'ok' : 'failed',
              durationMs: Number.isFinite(durationMs) && durationMs > 0 ? durationMs : undefined,
              error: error || undefined,
            };
          } else {
            toolStates.push({
              key: callId || `${toolName}#${toolCounter + 1}`,
              name: toolName,
              status: ok ? 'ok' : 'failed',
              durationMs: Number.isFinite(durationMs) && durationMs > 0 ? durationMs : undefined,
              error: error || undefined,
            });
          }
          renderStreamingPlaceholder();
          return;
        }
        if (eventType === 'assistant.delta') {
          const delta = String(payload.delta || '');
          if (delta) {
            assistantText += delta;
            scheduleAssistantPlaceholder();
          }
          return;
        }
        if (eventType === 'assistant.done') {
          const text = String(payload.text || '');
          if (text) assistantText = text;
          scheduleAssistantPlaceholder();
          return;
        }
        if (eventType === 'job.done') {
          clearAssistantRenderTimer();
          const text = String(payload.reply || assistantText || '');
          finishSuccess(text);
          stopped = true;
          return;
        }
        if (eventType === 'job.failed' || eventType === 'job.cancelled') {
          clearAssistantRenderTimer();
          const err = String(payload.error_detail || payload.error || '请求失败');
          finishFailure(err);
          stopped = true;
        }
      };
      while (!stopped) {
        if (!pendingChatJobRef.current?.job_id) return;
        try {
          const url = new URL(`${apiBase}/chat/stream`);
          url.searchParams.set('job_id', pendingChatJob.job_id);
          if (cursor > 0) url.searchParams.set('last_event_id', String(cursor));
          const res = await fetch(url.toString(), {
            signal: controller.signal,
            headers: { Accept: 'text/event-stream' },
          });
          if (!res.ok || !res.body) {
            const text = await res.text();
            throw new Error(text || `状态码 ${res.status}`);
          }
          const reader = res.body.getReader();
          const decoder = new TextDecoder('utf-8');
          let buffer = '';
          let sawEventInCurrentStream = false;
          while (!stopped) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const normalized = buffer.replace(/\r/g, '');
            const parts = normalized.split('\n\n');
            buffer = parts.pop() || '';
            for (const raw of parts) {
              const block = raw.trim();
              if (!block || block.startsWith(':')) continue;
              let eventType = '';
              let eventId = 0;
              const dataLines: string[] = [];
              for (const line of block.split('\n')) {
                if (line.startsWith('event:')) {
                  eventType = line.slice(6).trim();
                } else if (line.startsWith('id:')) {
                  const parsed = Number(line.slice(3).trim());
                  if (Number.isFinite(parsed) && parsed > 0) eventId = parsed;
                } else if (line.startsWith('data:')) {
                  dataLines.push(line.slice(5).trim());
                }
              }
              if (!dataLines.length) continue;
              const rawData = dataLines.join('\n');
              const payloadEnvelope = parseChatStreamEnvelope(rawData);
              if (!payloadEnvelope) continue;
              if (payloadEnvelope.eventVersion !== CHAT_STREAM_EVENT_VERSION) {
                clearAssistantRenderTimer();
                setPlaceholderContent('检测到新版流协议，已自动切换到稳态轮询…');
                startFallbackPolling();
                return;
              }
              const finalType = String(eventType || payloadEnvelope.eventType || '').trim();
              if (!finalType) continue;
              const payload = payloadEnvelope.payload;
              const finalEventId = Number(payloadEnvelope.eventId ?? eventId ?? 0);
              if (!Number.isFinite(finalEventId) || finalEventId <= cursor) continue;
              sawEventInCurrentStream = true;
              applyStreamEvent(finalType, payload, finalEventId);
              if (stopped) break;
            }
          }
          if (stopped || !pendingChatJobRef.current?.job_id) return;
          const statusData = await fetchTeacherChatJobStatus(
            apiBase,
            pendingChatJob.job_id,
            controller.signal,
          );
          if (Array.isArray(statusData.execution_timeline)) {
            setExecutionTimeline(statusData.execution_timeline);
          }
          if (statusData.status === 'done') {
            clearAssistantRenderTimer();
            finishSuccess(statusData.reply || assistantText || '');
            stopped = true;
            return;
          }
          if (statusData.status === 'failed' || statusData.status === 'cancelled') {
            clearAssistantRenderTimer();
            finishFailure(statusData.error_detail || statusData.error || '请求失败');
            stopped = true;
            return;
          }
          const workflowHint = resolveWorkflowHint(statusData, skillList);
          if (workflowHint) setComposerWarning(workflowHint);
          const lanePos = Number(statusData.lane_queue_position || 0);
          const laneSize = Number(statusData.lane_queue_size || 0);
          if (statusData.status === 'queued') {
            applyTeacherChatQueuedHints(lanePos, laneSize, setChatQueueHint, setPendingStreamStage);
          } else if (statusData.status === 'processing') {
            applyTeacherChatProcessingHints(setChatQueueHint, setPendingStreamStage);
          }
          if (sawEventInCurrentStream) reconnectAttempts = 0;
          reconnectAttempts += 1;
          if (reconnectAttempts >= 4) {
            startFallbackPolling();
            return;
          }
          await streamSleep(Math.min(3000, reconnectAttempts * 800));
        } catch (err: unknown) {
          clearAssistantRenderTimer();
          if (controller.signal.aborted || stopped) return;
          reconnectAttempts += 1;
          if (reconnectAttempts >= 4) {
            startFallbackPolling();
            return;
          }
          await streamSleep(Math.min(3000, reconnectAttempts * 800));
        }
      }
      clearAssistantRenderTimer();
    };
    void runStream();
    return () => {
      stopped = true;
      controller.abort();
      setChatQueueHint('');
      setPendingStreamStage('');
      setPendingToolRuns([]);
      if (pollCleanup) pollCleanup();
    };
  }, [
    pendingChatJob,
    pendingChatJob?.job_id,
    apiBase,
    authToken,
    refreshTeacherSessions,
    activeSessionId,
    setMessages,
    setPendingChatJob,
    setChatQueueHint,
    setPendingStreamStage,
    setPendingToolRuns,
    setExecutionTimeline,
    setSending,
    setComposerWarning,
    skillList,
    pendingChatJobRef,
    setToolConfirm,
  ]);
}
