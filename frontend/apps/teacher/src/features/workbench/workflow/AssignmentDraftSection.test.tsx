import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import AssignmentDraftSection from './AssignmentDraftSection';
import type { UploadDraft } from '../../../appTypes';

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
} as UploadDraft;

describe('AssignmentDraftSection', () => {
  it('draft_requirement_fields_associate_labels', () => {
    render(
      <AssignmentDraftSection
        uploadDraft={draft}
        uploadJobInfo={null}
        draftPanelCollapsed={false}
        setDraftPanelCollapsed={vi.fn()}
        draftActionError=""
        draftActionStatus=""
        draftSaving={false}
        uploadConfirming={false}
        saveDraft={vi.fn()}
        handleConfirmUpload={vi.fn()}
        formatDraftSummary={() => ''}
        formatMissingRequirements={() => ''}
        updateDraftRequirement={vi.fn()}
        updateDraftQuestion={vi.fn()}
        misconceptionsText=""
        setMisconceptionsText={vi.fn()}
        setMisconceptionsDirty={vi.fn()}
        parseCommaList={(v) =>
          String(v)
            .split(/[，,]/)
            .map((s) => s.trim())
            .filter(Boolean)
        }
        parseLineList={(v) =>
          String(v)
            .split('\n')
            .map((s) => s.trim())
            .filter(Boolean)
        }
        difficultyLabel={() => ''}
        difficultyOptions={[]}
        normalizeDifficulty={() => ''}
        questionShowCount={3}
        setQuestionShowCount={vi.fn()}
        stopKeyPropagation={vi.fn()}
      />,
    );
    expect(screen.getByLabelText('1) 学科')).toBeTruthy();
    expect(screen.getByLabelText('1) 本节课主题')).toBeTruthy();
    expect(screen.getByLabelText('2) 年级')).toBeTruthy();
  });

  it('draft error uses role alert', () => {
    render(
      <AssignmentDraftSection
        uploadDraft={draft}
        uploadJobInfo={null}
        draftPanelCollapsed={false}
        setDraftPanelCollapsed={vi.fn()}
        draftActionError="保存失败"
        draftActionStatus=""
        draftSaving={false}
        uploadConfirming={false}
        saveDraft={vi.fn()}
        handleConfirmUpload={vi.fn()}
        formatDraftSummary={() => ''}
        formatMissingRequirements={() => ''}
        updateDraftRequirement={vi.fn()}
        updateDraftQuestion={vi.fn()}
        misconceptionsText=""
        setMisconceptionsText={vi.fn()}
        setMisconceptionsDirty={vi.fn()}
        parseCommaList={() => []}
        parseLineList={() => []}
        difficultyLabel={() => ''}
        difficultyOptions={[]}
        normalizeDifficulty={() => ''}
        questionShowCount={3}
        setQuestionShowCount={vi.fn()}
        stopKeyPropagation={vi.fn()}
      />,
    );
    expect(screen.getByRole('alert').textContent).toContain('保存失败');
  });
});
