import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useAssignmentWorkflow } from './useAssignmentWorkflow';
import type { FormEvent } from 'react';

const noop = () => undefined;

const baseParams = {
  apiBase: 'http://localhost:8000',
  assignmentKind: 'problem_set' as const,
  contentSource: 'upload' as const,
  completionRequiresSubmission: true,
  completionRequiresDiscussion: false,
  completionAllowPractice: true,
  setAssignmentKind: noop,
  setContentSource: noop,
  setCompletionRequiresSubmission: noop as (value: boolean) => void,
  setCompletionRequiresDiscussion: noop as (value: boolean) => void,
  setCompletionAllowPractice: noop as (value: boolean) => void,
  uploadMode: 'assignment',
  uploadAssignmentId: 'HW-1',
  uploadDate: '',
  uploadDueAt: '2026-08-29',
  uploadSubjectId: 'math',
  uploadScope: 'public',
  uploadClassName: '',
  uploadStudentIds: '',
  uploadFiles: [new File(['x'], 'paper.pdf', { type: 'application/pdf' })],
  uploadAnswerFiles: [] as File[],
  uploading: false,
  uploadStatus: '',
  uploadError: '',
  uploadCardCollapsed: false,
  uploadJobId: '',
  uploadJobInfo: null,
  uploadConfirming: false,
  uploadStatusPollNonce: 0,
  uploadDraft: null,
  draftPanelCollapsed: false,
  draftLoading: false,
  draftError: '',
  questionShowCount: 20,
  draftSaving: false,
  draftActionStatus: '',
  draftActionError: '',
  misconceptionsText: '',
  misconceptionsDirty: false,
  progressPanelCollapsed: true,
  progressAssignmentId: '',
  progressLoading: false,
  progressError: '',
  progressData: null,
  progressOnlyIncomplete: true,
  setUploadError: noop as (value: string) => void,
  setUploadStatus: noop as (value: string | ((prev: string) => string)) => void,
  setUploadJobId: noop,
  setUploadJobInfo: noop as () => void,
  setUploadDraft: noop as () => void,
  setUploadFiles: noop as (value: File[]) => void,
  setUploadAnswerFiles: noop as (value: File[]) => void,
  setUploading: noop as (value: boolean) => void,
  setUploadCardCollapsed: noop as () => void,
  setUploadConfirming: noop as (value: boolean) => void,
  setUploadStatusPollNonce: noop as () => void,
  setDraftPanelCollapsed: noop as () => void,
  setDraftLoading: noop as (value: boolean) => void,
  setDraftError: noop,
  setQuestionShowCount: noop as () => void,
  setDraftSaving: noop as (value: boolean) => void,
  setDraftActionStatus: noop,
  setDraftActionError: noop,
  setMisconceptionsText: noop,
  setMisconceptionsDirty: noop as (value: boolean) => void,
  setProgressPanelCollapsed: noop as () => void,
  setProgressAssignmentId: noop,
  setProgressLoading: noop as (value: boolean) => void,
  setProgressError: noop,
  setProgressData: noop as () => void,
};

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('useAssignmentWorkflow upload form', () => {
  it('sends subject_id and due_at on assignment upload start', async () => {
    const appended: Array<[string, string]> = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init?: RequestInit) => {
        const body = init?.body as FormData;
        for (const key of [
          'assignment_id',
          'subject_id',
          'due_at',
          'date',
          'scope',
          'assignment_kind',
        ]) {
          const value = body.get(key);
          if (typeof value === 'string') appended.push([key, value]);
        }
        return {
          ok: true,
          json: async () => ({ ok: true, job_id: 'job-1', message: 'queued' }),
        };
      }),
    );

    const { result } = renderHook(() => useAssignmentWorkflow(baseParams));
    await act(async () => {
      await result.current.handleUploadAssignment({ preventDefault: () => undefined } as FormEvent);
    });

    expect(appended).toContainEqual(['assignment_id', 'HW-1']);
    expect(appended).toContainEqual(['subject_id', 'math']);
    expect(appended).toContainEqual(['due_at', '2026-08-29']);
    expect(appended).toContainEqual(['assignment_kind', 'problem_set']);
    expect(appended.some(([key]) => key === 'date')).toBe(false);
  });
});

describe('useAssignmentWorkflow folder draft locator', () => {
  const folderDraft = {
    assignment_id: 'HW-FOLDER',
    date: '2026-10-10',
    scope: 'public' as const,
    questions: [{ stem: 'q1' }],
    requirements: { subject: 'math', topic: '力学', grade_level: '高二' },
    requirements_missing: [],
  };

  it('saves and confirms by assignment_id when job_id is missing', async () => {
    window.localStorage.removeItem('teacherActiveUpload');
    const calls: Array<{ url: string; body: Record<string, unknown> }> = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        const body = JSON.parse(String(init?.body || '{}')) as Record<string, unknown>;
        calls.push({ url: String(url), body });
        return {
          ok: true,
          json: async () => ({ ok: true, message: 'ok', assignment_id: 'HW-FOLDER' }),
          text: async () => '',
        };
      }),
    );

    const { result } = renderHook(() =>
      useAssignmentWorkflow({
        ...baseParams,
        uploadJobId: '',
        uploadJobInfo: null,
        uploadDraft: folderDraft,
        setUploadError: vi.fn(),
        setDraftActionError: vi.fn(),
        setDraftActionStatus: vi.fn(),
        setDraftSaving: vi.fn(),
        setUploadConfirming: vi.fn(),
        setUploadStatus: vi.fn(),
        setUploadDraft: vi.fn(),
        setMisconceptionsDirty: vi.fn(),
        setProgressAssignmentId: vi.fn(),
        setProgressPanelCollapsed: vi.fn(),
      }),
    );

    await act(async () => {
      await result.current.saveDraft(folderDraft);
    });
    expect(calls[0]?.url).toContain('/assignment/upload/draft/save');
    expect(calls[0]?.body.assignment_id).toBe('HW-FOLDER');
    expect(calls[0]?.body.job_id).toBeUndefined();

    await act(async () => {
      await result.current.handleConfirmUpload();
    });
    const confirm = calls.find((call) => call.url.includes('/assignment/upload/confirm'));
    expect(confirm).toBeTruthy();
    expect(confirm?.body.job_id).toBeUndefined();
    expect(confirm?.body.assignment_id).toBe('HW-FOLDER');
    expect(confirm?.body.strict_requirements).toBe(true);
    expect(confirm?.body.completion_policy_override).toEqual({
      requires_submission: true,
      requires_discussion: false,
      allow_practice: true,
    });
  });

  it('from-bank sets a draft without job_id', async () => {
    const captured: { draft: Record<string, unknown> | null } = { draft: null };
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          ok: true,
          assignment_id: 'HW-BANK',
          draft: {
            assignment_id: 'HW-BANK',
            questions: [{ stem: 'bank-q' }],
            requirements: {},
            requirements_missing: ['subject'],
            assignment_kind: 'problem_set',
            content_source: 'bank',
          },
        }),
        text: async () => '',
      })),
    );

    const { result } = renderHook(() =>
      useAssignmentWorkflow({
        ...baseParams,
        uploadAssignmentId: 'HW-BANK',
        setUploadDraft: (value) => {
          captured.draft =
            typeof value === 'function'
              ? value(captured.draft as never)
              : (value as Record<string, unknown>);
        },
        setUploading: vi.fn(),
        setUploadError: vi.fn(),
        setUploadStatus: vi.fn(),
        setDraftActionError: vi.fn(),
        setDraftActionStatus: vi.fn(),
        setUploadJobId: vi.fn(),
        setUploadJobInfo: vi.fn(),
        setDraftPanelCollapsed: vi.fn(),
        setQuestionShowCount: vi.fn(),
        setMisconceptionsDirty: vi.fn(),
      }),
    );

    await act(async () => {
      await result.current.handleFromBank({ kp: '力学', count: 5 });
    });
    expect(captured.draft).toBeTruthy();
    expect(captured.draft?.job_id).toBeUndefined();
    expect(captured.draft?.assignment_id).toBe('HW-BANK');
    expect(captured.draft?.content_source).toBe('bank');
  });
});

describe('useAssignmentWorkflow saveStudentGrade', () => {
  it('posts grade against loaded progress assignment_id not the typed input', async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (String(url).includes('/grade')) {
        return { ok: true, json: async () => ({ ok: true }), text: async () => '' };
      }
      return {
        ok: true,
        json: async () => ({ ok: true, assignment_id: 'HW-LOADED', students: [] }),
      };
    });
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() =>
      useAssignmentWorkflow({
        ...baseParams,
        progressAssignmentId: 'HW-TYPED',
        progressData: { ok: true, assignment_id: 'HW-LOADED', students: [] },
        setProgressError: vi.fn(),
        setProgressLoading: vi.fn(),
        setProgressData: vi.fn(),
      }),
    );

    await act(async () => {
      await result.current.saveStudentGrade('S1', { override_score: null });
    });

    const gradeCall = fetchMock.mock.calls.find(([url]) => String(url).includes('/grade'));
    expect(String(gradeCall?.[0])).toContain('/teacher/assignment/HW-LOADED/student/S1/grade');
    expect(String(gradeCall?.[0])).not.toContain('HW-TYPED');
  });
});
