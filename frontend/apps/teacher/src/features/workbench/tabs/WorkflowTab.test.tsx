import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import WorkflowTab, { type WorkflowTabProps } from './WorkflowTab';

vi.mock('../workflow/WorkflowSummaryCard', () => ({
  default: () => <div>workflow-summary-card</div>,
}));

vi.mock('../workflow/UploadSection', () => ({
  default: (props: { assignmentKind?: string }) => (
    <div>workflow-upload-section {props.assignmentKind}</div>
  ),
}));

vi.mock('../workflow/BankPickForm', () => ({
  default: () => <div>workflow-bank-pick-form</div>,
}));

vi.mock('../workflow/AiDraftForm', () => ({
  default: () => <div>workflow-ai-draft-form</div>,
}));

vi.mock('../workflow/AssignmentProgressSection', () => ({
  default: () => <div>workflow-progress-section</div>,
}));

vi.mock('../workflow/AssignmentDraftSection', () => ({
  default: () => <div>workflow-assignment-draft-section</div>,
}));

vi.mock('../workflow/WorkflowTimeline', () => ({
  default: () => <div>workflow-timeline-section</div>,
}));

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const buildProps = (): WorkflowTabProps =>
  ({
    draftLoading: false,
    draftError: '',
    uploadDraft: {
      job_id: 'job1',
      assignment_id: 'HW-1',
      date: '2026-03-14',
      scope: 'public',
      delivery_mode: 'pdf',
      requirements: {
        subject: '物理',
        topic: '受力分析',
        grade_level: '高二',
        class_level: '中等',
        core_concepts: [],
        typical_problem: '',
        misconceptions: [],
        duration_minutes: 40,
        preferences: [],
        extra_constraints: '',
      },
      requirements_missing: [],
      questions: [],
      draft_saved: true,
    } as never,
    activeWorkflowIndicator: {
      label: '待审核',
      tone: 'active',
      steps: [
        { key: 'upload', label: '上传文件', state: 'done' },
        { key: 'parse', label: '解析', state: 'done' },
        { key: 'review', label: '审核草稿', state: 'active' },
        { key: 'confirm', label: '发布草稿', state: 'todo' },
      ],
    },
    formatUploadJobSummary: () => 'upload-summary',
    formatProgressSummary: () => 'progress-summary',
    uploadJobInfo: null,
    uploadAssignmentId: 'HW-1',
    scrollToWorkflowSection: () => undefined,
    refreshWorkflowWorkbench: () => undefined,
    progressData: null,
    progressAssignmentId: 'HW-1',
    progressLoading: false,
    fetchAssignmentProgress: async () => undefined,
    uploading: false,
    progressPanelCollapsed: false,
    setProgressPanelCollapsed: () => undefined,
    setProgressAssignmentId: () => undefined,
    progressOnlyIncomplete: false,
    setProgressOnlyIncomplete: () => undefined,
    progressError: '',
    draftSaving: false,
    uploadConfirming: false,
    executionTimeline: [],
    uploadCardCollapsed: false,
    setUploadCardCollapsed: () => undefined,
    handleUploadAssignment: async () => undefined,
    setUploadAssignmentId: () => undefined,
    uploadDate: '2026-03-14',
    setUploadDate: () => undefined,
    uploadDueAt: '',
    setUploadDueAt: () => undefined,
    uploadSubjectId: 'generic',
    setUploadSubjectId: () => undefined,
    uploadScope: 'public',
    setUploadScope: () => undefined,
    uploadClassName: '',
    setUploadClassName: () => undefined,
    uploadStudentIds: '',
    setUploadStudentIds: () => undefined,
    setUploadFiles: () => undefined,
    setUploadAnswerFiles: () => undefined,
    uploadError: '',
    uploadStatus: '',
    stopKeyPropagation: () => undefined,
    draftPanelCollapsed: false,
    setDraftPanelCollapsed: () => undefined,
    draftActionError: '',
    draftActionStatus: '',
    saveDraft: async () => undefined,
    handleConfirmUpload: async () => undefined,
    formatDraftSummary: () => 'draft-summary',
    formatMissingRequirements: () => 'missing',
    updateDraftRequirement: () => undefined,
    updateDraftQuestion: () => undefined,
    misconceptionsText: '',
    setMisconceptionsText: () => undefined,
    setMisconceptionsDirty: () => undefined,
    parseCommaList: () => [],
    parseLineList: () => [],
    difficultyLabel: () => '',
    difficultyOptions: [],
    normalizeDifficulty: () => 'medium',
    questionShowCount: 3,
    setQuestionShowCount: () => undefined,
    assignmentKind: 'problem_set',
    contentSource: 'upload',
    requestAssignmentKindChange: () => undefined,
    requestContentSourceChange: () => undefined,
    pendingPickerChange: null,
    confirmPendingPickerChange: () => undefined,
    cancelPendingPickerChange: () => undefined,
    handleFromBank: async () => undefined,
    handleGenerate: async () => undefined,
    completionRequiresSubmission: true,
    setCompletionRequiresSubmission: () => undefined,
    completionRequiresDiscussion: false,
    setCompletionRequiresDiscussion: () => undefined,
    completionAllowPractice: true,
    setCompletionAllowPractice: () => undefined,
  }) as unknown as WorkflowTabProps;

describe('WorkflowTab', () => {
  it('groups workflow content into current action and supplementary sections', () => {
    render(<WorkflowTab {...buildProps()} />);

    expect(screen.getByText('先完成必做动作，再展开补充参考。')).toBeTruthy();
    expect(screen.getByText('workflow-summary-card')).toBeTruthy();
    expect(screen.getByText('工作流编辑')).toBeTruthy();
    expect(screen.getByText('先完成必做动作，再展开补充参考。')).toBeTruthy();
    expect(screen.getByText('必做动作')).toBeTruthy();
    expect(screen.getByText('必做')).toBeTruthy();
    expect(screen.getByText('按下面的主线动作继续处理。')).toBeTruthy();
    expect(screen.queryByText('下一步：继续审核草稿并发布草稿')).toBeNull();
    expect(screen.getByTestId('workflow-kind-source-picker')).toBeTruthy();
    expect(screen.getByText('workflow-upload-section problem_set')).toBeTruthy();
    expect(screen.queryByText('workflow-bank-pick-form')).toBeNull();
    expect(screen.getByText('workflow-assignment-draft-section')).toBeTruthy();
    expect(screen.getByText('补充参考')).toBeTruthy();
    expect(screen.getByText('按需查看')).toBeTruthy();
    expect(screen.getByText('workflow-progress-section')).toBeTruthy();
    expect(screen.queryByText('workflow-analysis-section')).toBeNull();
    expect(screen.queryByText('workflow-video-analysis-section')).toBeNull();
    expect(screen.queryByText('统一分析报告')).toBeNull();
    expect(screen.getByText('workflow-timeline-section')).toBeTruthy();
    expect(
      screen.getByTestId('teacher-workflow-primary-stage').getAttribute('data-workflow-tier'),
    ).toBe('primary');
    expect(
      screen.getByTestId('teacher-workflow-secondary-stage').getAttribute('data-workflow-tier'),
    ).toBe('supporting');

    const progressSection = screen.getByText('workflow-progress-section');
    const timelineSection = screen.getByText('workflow-timeline-section');

    expect(
      progressSection.compareDocumentPosition(timelineSection) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it('passes assignmentKind into UploadSection', () => {
    render(<WorkflowTab {...buildProps()} assignmentKind="scenario" />);
    expect(screen.getByText('workflow-upload-section scenario')).toBeTruthy();
  });

  it('disables bank unless problem_set', () => {
    const { rerender } = render(<WorkflowTab {...buildProps()} />);
    expect((screen.getByTestId('workflow-source-bank') as HTMLInputElement).disabled).toBe(false);

    rerender(<WorkflowTab {...buildProps()} assignmentKind="scenario" />);
    const bank = screen.getByTestId('workflow-source-bank') as HTMLInputElement;
    expect(bank.disabled).toBe(true);
    expect(bank.title).toBe('题库仅用于做题作业');
  });

  it('shows bank form when source is bank', () => {
    render(<WorkflowTab {...buildProps()} contentSource="bank" />);
    expect(screen.getByText('workflow-bank-pick-form')).toBeTruthy();
    expect(screen.queryByText('workflow-upload-section')).toBeNull();
    expect(screen.getByText('workflow-assignment-draft-section')).toBeTruthy();
  });

  it('does not mount bank form when kind is not problem_set', () => {
    render(<WorkflowTab {...buildProps()} assignmentKind="scenario" contentSource="bank" />);
    expect(screen.queryByText('workflow-bank-pick-form')).toBeNull();
  });
});
