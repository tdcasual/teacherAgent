import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import UploadSection from './UploadSection'

describe('UploadSection', () => {
  it('offers a static subject list and optional due_at, not a roster dropdown', () => {
    render(
      <UploadSection
        uploadMode="assignment"
        setUploadMode={vi.fn()}
        uploadCardCollapsed={false}
        setUploadCardCollapsed={vi.fn()}
        formatUploadJobSummary={() => 'upload'}
        formatExamJobSummary={() => 'exam'}
        uploadJobInfo={null}
        uploadAssignmentId="HW-1"
        examJobInfo={null}
        examId=""
        handleUploadAssignment={vi.fn()}
        handleUploadExam={vi.fn()}
        setUploadAssignmentId={vi.fn()}
        uploadDate=""
        setUploadDate={vi.fn()}
        uploadDueAt=""
        setUploadDueAt={vi.fn()}
        uploadSubjectId="generic"
        setUploadSubjectId={vi.fn()}
        uploadScope="public"
        setUploadScope={vi.fn()}
        uploadClassName=""
        setUploadClassName={vi.fn()}
        uploadStudentIds=""
        setUploadStudentIds={vi.fn()}
        setUploadFiles={vi.fn()}
        setUploadAnswerFiles={vi.fn()}
        uploading={false}
        uploadError=""
        uploadStatus=""
        setExamId={vi.fn()}
        examDate=""
        setExamDate={vi.fn()}
        examClassName=""
        setExamClassName={vi.fn()}
        setExamPaperFiles={vi.fn()}
        setExamAnswerFiles={vi.fn()}
        setExamScoreFiles={vi.fn()}
        examUploading={false}
        examUploadError=""
        examUploadStatus=""
      />,
    )

    const subject = screen.getByLabelText('学科') as HTMLSelectElement
    expect(subject.value).toBe('generic')
    expect(Array.from(subject.options).map((option) => option.value)).toEqual([
      'physics',
      'math',
      'generic',
    ])
    expect(screen.getByLabelText('截止日期（可选）')).toBeTruthy()
    expect(screen.getByRole('button', { name: '考试', exact: true })).toBeTruthy()
  })
})
