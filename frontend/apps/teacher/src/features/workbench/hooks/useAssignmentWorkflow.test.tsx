import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useAssignmentWorkflow } from './useAssignmentWorkflow'
import type { FormEvent } from 'react'

const noop = () => undefined

const baseParams = {
  apiBase: 'http://localhost:8000',
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
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('useAssignmentWorkflow upload form', () => {
  it('sends subject_id and due_at on assignment upload start', async () => {
    const appended: Array<[string, string]> = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init?: RequestInit) => {
        const body = init?.body as FormData
        for (const key of ['assignment_id', 'subject_id', 'due_at', 'date', 'scope']) {
          const value = body.get(key)
          if (typeof value === 'string') appended.push([key, value])
        }
        return {
          ok: true,
          json: async () => ({ ok: true, job_id: 'job-1', message: 'queued' }),
        }
      }),
    )

    const { result } = renderHook(() => useAssignmentWorkflow(baseParams))
    await act(async () => {
      await result.current.handleUploadAssignment({ preventDefault: () => undefined } as FormEvent)
    })

    expect(appended).toContainEqual(['assignment_id', 'HW-1'])
    expect(appended).toContainEqual(['subject_id', 'math'])
    expect(appended).toContainEqual(['due_at', '2026-08-29'])
    expect(appended.some(([key]) => key === 'date')).toBe(false)
  })
})

describe('useAssignmentWorkflow saveStudentGrade', () => {
  it('posts grade against loaded progress assignment_id not the typed input', async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (String(url).includes('/grade')) {
        return { ok: true, json: async () => ({ ok: true }), text: async () => '' }
      }
      return {
        ok: true,
        json: async () => ({ ok: true, assignment_id: 'HW-LOADED', students: [] }),
      }
    })
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderHook(() =>
      useAssignmentWorkflow({
        ...baseParams,
        progressAssignmentId: 'HW-TYPED',
        progressData: { ok: true, assignment_id: 'HW-LOADED', students: [] },
        setProgressError: vi.fn(),
        setProgressLoading: vi.fn(),
        setProgressData: vi.fn(),
      }),
    )

    await act(async () => {
      await result.current.saveStudentGrade('S1', { override_score: null })
    })

    const gradeCall = fetchMock.mock.calls.find(([url]) => String(url).includes('/grade'))
    expect(String(gradeCall?.[0])).toContain('/teacher/assignment/HW-LOADED/student/S1/grade')
    expect(String(gradeCall?.[0])).not.toContain('HW-TYPED')
  })
})
