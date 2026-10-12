import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import AssignmentDraftSection from './AssignmentDraftSection';
import type { AssignmentKind, UploadDraft } from '../../../appTypes';
import type { AssignmentDraftSectionProps } from '../../../types/workflow';

afterEach(() => {
  cleanup();
});

const draft: UploadDraft = {
  assignment_id: 'HW1',
  date: '2026-10-10',
  scope: 'class',
  class_name: '高二1班',
  student_ids: ['S1'],
  questions: [],
  delivery_mode: 'pdf',
  requirements_missing: [],
  requirements: {
    subject: '物理',
    topic: '力学',
    grade_level: '高二',
    class_level: '中等',
    core_concepts: ['力'],
    typical_problem: '例',
    duration_minutes: 40,
    preferences: [],
    extra_constraints: '',
  },
};

const baseProps = (): Omit<AssignmentDraftSectionProps, 'uploadDraft'> & {
  draftSaving: boolean;
  uploadConfirming: boolean;
} => ({
  uploadJobInfo: null,
  draftPanelCollapsed: false,
  setDraftPanelCollapsed: vi.fn(),
  draftActionError: '',
  draftActionStatus: '',
  draftSaving: false,
  uploadConfirming: false,
  saveDraft: vi.fn(),
  handleConfirmUpload: vi.fn(),
  formatDraftSummary: () => '',
  formatMissingRequirements: (missing) => (missing || []).join('、'),
  updateDraftRequirement: vi.fn(),
  updateDraftQuestion: vi.fn(),
  misconceptionsText: '',
  setMisconceptionsText: vi.fn(),
  setMisconceptionsDirty: vi.fn(),
  parseCommaList: (v) =>
    String(v)
      .split(/[，,]/)
      .map((s) => s.trim())
      .filter(Boolean),
  parseLineList: (v) =>
    String(v)
      .split('\n')
      .map((s) => s.trim())
      .filter(Boolean),
  difficultyLabel: () => '',
  difficultyOptions: [],
  normalizeDifficulty: () => '',
  questionShowCount: 3,
  setQuestionShowCount: vi.fn(),
  stopKeyPropagation: vi.fn(),
  assignmentKind: 'problem_set',
  completionRequiresSubmission: true,
  setCompletionRequiresSubmission: vi.fn(),
  completionRequiresDiscussion: false,
  setCompletionRequiresDiscussion: vi.fn(),
  completionAllowPractice: true,
  setCompletionAllowPractice: vi.fn(),
});

const renderDraft = (
  current: UploadDraft,
  kind: AssignmentKind = 'problem_set',
  extra: Partial<ReturnType<typeof baseProps>> = {},
) =>
  render(
    <AssignmentDraftSection
      {...baseProps()}
      {...extra}
      assignmentKind={kind}
      uploadDraft={{ ...current, assignment_kind: kind }}
    />,
  );

describe('AssignmentDraftSection', () => {
  it('draft_requirement_fields_associate_labels', () => {
    renderDraft(draft);
    expect(screen.getByLabelText('1) 学科')).toBeTruthy();
    expect(screen.getByLabelText('1) 本节课主题')).toBeTruthy();
    expect(screen.getByLabelText('2) 年级')).toBeTruthy();
  });

  it('draft error uses role alert', () => {
    renderDraft(draft, 'problem_set', { draftActionError: '保存失败' });
    expect(screen.getByRole('alert').textContent).toContain('保存失败');
  });

  it('scenario missing brief cannot publish', () => {
    renderDraft(
      {
        ...draft,
        questions: [],
        requirements: { subject: '物理', topic: '力学', grade_level: '高二', brief: '' },
        requirements_missing: ['brief'],
      },
      'scenario',
    );
    const confirm = screen.getByTestId('assignment-confirm-button') as HTMLButtonElement;
    expect(confirm.disabled).toBe(true);
    expect(confirm.title).toMatch(/brief|作业说明/);
    expect(screen.getByLabelText('作业说明')).toBeTruthy();
    expect(screen.queryByLabelText('5) 易错点（每行一条，至少 4 条）')).toBeNull();
    expect(screen.queryByText('题目与答案（可编辑）')).toBeNull();
    expect(screen.queryByTestId('draft-allow-practice')).toBeNull();
    expect(screen.getByText('需要讨论（陪练提示，不作为完成条件）')).toBeTruthy();
    expect(screen.getByText(/补全后才能发布/)).toBeTruthy();
    expect(screen.getByTestId('draft-rubric')).toBeTruthy();
    expect(screen.getByLabelText('量规（可选，每行一条）')).toBeTruthy();
  });

  it('problem_set shows allow_practice and eight-point fields', () => {
    renderDraft({
      ...draft,
      questions: [{ stem: '题干', answer: '答案' }],
    });
    expect(screen.getByTestId('draft-allow-practice')).toBeTruthy();
    expect(screen.getByLabelText('5) 易错点（每行一条，至少 4 条）')).toBeTruthy();
    expect(screen.queryByTestId('draft-rubric')).toBeNull();
    expect(screen.getByText(/后再发布/)).toBeTruthy();
    expect(screen.queryByText(/后再创建/)).toBeNull();
  });

  it('confirm button text is 发布草稿', () => {
    renderDraft(draft);
    expect(screen.getByTestId('assignment-confirm-button').textContent).toBe('发布草稿');
    expect(screen.getByText('作业要求已补全，可发布。')).toBeTruthy();
  });

  it('confirm button uses publish copy while confirming and after success', () => {
    const { rerender } = renderDraft(draft, 'problem_set', { uploadConfirming: true });
    expect(screen.getByTestId('assignment-confirm-button').textContent).toBe('发布中…');

    rerender(
      <AssignmentDraftSection
        {...baseProps()}
        assignmentKind="problem_set"
        uploadDraft={{ ...draft, assignment_kind: 'problem_set' }}
        uploadJobInfo={{ job_id: 'job-1', status: 'created' }}
      />,
    );
    const confirmed = screen.getByTestId('assignment-confirm-button') as HTMLButtonElement;
    expect(confirmed.textContent).toBe('已发布');
    expect(confirmed.title).toBe('作业已发布，无需重复发布');
  });

  it('non-problem_set draft-rubric writes requirements.rubric', () => {
    const updateDraftRequirement = vi.fn();
    renderDraft(
      {
        ...draft,
        questions: [],
        requirements: { subject: '物理', topic: '力学', grade_level: '高二', brief: '情景说明' },
      },
      'scenario',
      { updateDraftRequirement },
    );
    fireEvent.change(screen.getByTestId('draft-rubric'), {
      target: { value: '- 能指出情景约束' },
    });
    expect(updateDraftRequirement).toHaveBeenCalledWith('rubric', '- 能指出情景约束');
  });
});
