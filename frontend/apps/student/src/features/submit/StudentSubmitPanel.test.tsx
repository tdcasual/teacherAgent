import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import StudentSubmitPanel from './StudentSubmitPanel'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

const pdfFile = () => new File(['pdf-bytes'], 'hw.pdf', { type: 'application/pdf' })

describe('StudentSubmitPanel', () => {
  it('posts selected files to /student/submit with assignment_id and without auto_assignment', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({
      ok: true,
      submitted: true,
      assignment_id: 'HW_1',
      official_score: 9,
      attempt_id: 'submission_ok',
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)

    render(
      <StudentSubmitPanel
        apiBase="http://localhost:8000"
        studentId="S1"
        assignmentId="HW_1"
        assignmentTitle="力学练习"
        chatFiles={[]}
        onClose={() => undefined}
        onSubmitted={() => undefined}
      />,
    )

    fireEvent.change(screen.getByLabelText('选择提交文件'), { target: { files: [pdfFile()] } })
    fireEvent.click(screen.getByRole('button', { name: '提交作业' }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toBe('http://localhost:8000/student/submit')
    const body = init?.body as FormData
    expect(body.get('assignment_id')).toBe('HW_1')
    expect(body.get('student_id')).toBe('S1')
    expect(body.get('auto_assignment')).toBeNull()
    expect((body.get('files') as File).name).toBe('hw.pdf')
    expect(screen.getByTestId('student-submit-result').textContent).toContain('已提交')
    expect(screen.getByTestId('student-submit-result').textContent).toContain('9')
  })

  it('requires a second confirm before posting current chat attachments', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({
      ok: true,
      submitted: true,
      assignment_id: 'HW_1',
      official_score: 6,
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)
    const chatFile = pdfFile()

    render(
      <StudentSubmitPanel
        apiBase="http://localhost:8000"
        studentId="S1"
        assignmentId="HW_1"
        assignmentTitle="力学练习"
        chatFiles={[chatFile]}
        onClose={() => undefined}
        onSubmitted={() => undefined}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '把当前聊天附件作为本次提交' }))
    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.getByText('hw.pdf')).toBeTruthy()
    expect(screen.getByRole('button', { name: '确认提交' })).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: '确认提交' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const body = fetchMock.mock.calls[0][1]?.body as FormData
    expect((body.get('files') as File).name).toBe('hw.pdf')
  })

  it('hides chat reuse and disables confirm when there are no File blobs', () => {
    render(
      <StudentSubmitPanel
        apiBase="http://localhost:8000"
        studentId="S1"
        assignmentId="HW_1"
        assignmentTitle="力学练习"
        chatFiles={[]}
        onClose={() => undefined}
        onSubmitted={() => undefined}
      />,
    )
    expect(screen.queryByRole('button', { name: '把当前聊天附件作为本次提交' })).toBeNull()
  })

  it('shows a clear not-submitted banner when min_graded_total fails on HTTP 200', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
      ok: true,
      submitted: false,
      assignment_id: 'HW_1',
      reason: 'min_graded_total',
      official_score: null,
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })))

    render(
      <StudentSubmitPanel
        apiBase="http://localhost:8000"
        studentId="S1"
        assignmentId="HW_1"
        assignmentTitle="力学练习"
        chatFiles={[]}
        onClose={() => undefined}
        onSubmitted={() => undefined}
      />,
    )

    fireEvent.change(screen.getByLabelText('选择提交文件'), { target: { files: [pdfFile()] } })
    fireEvent.click(screen.getByRole('button', { name: '提交作业' }))

    await waitFor(() => expect(screen.getByTestId('student-submit-not-counted')).toBeTruthy())
    expect(screen.getByTestId('student-submit-not-counted').textContent).toContain('未记为提交')
    expect(screen.queryByTestId('student-submit-success')).toBeNull()
  })
})
