import { describe, expect, it } from 'vitest';
import {
  buildAssignmentWorkflowIndicator,
  buildTeacherWorkflowGuidance,
} from './workflowIndicators';

describe('workflowIndicators publish-draft copy', () => {
  it('confirm step and nextStepLabels use 发布草稿', () => {
    const indicator = buildAssignmentWorkflowIndicator({
      uploadJobId: '',
      uploading: false,
      uploadConfirming: false,
      uploadDraft: null,
      uploadError: '',
      draftError: '',
      draftActionError: '',
    });
    expect(indicator.steps.find((step) => step.key === 'confirm')?.label).toBe('发布草稿');

    expect(
      buildTeacherWorkflowGuidance({
        tone: 'error',
        activeStepKey: 'confirm',
        hasExecutionTimeline: false,
        hasProgressData: false,
      }).nextStepLabel,
    ).toContain('发布草稿');
    expect(
      buildTeacherWorkflowGuidance({
        tone: 'active',
        activeStepKey: 'review',
        hasExecutionTimeline: false,
        hasProgressData: false,
      }).nextStepLabel,
    ).toBe('下一步：继续审核草稿并发布草稿');
    expect(
      buildTeacherWorkflowGuidance({
        tone: 'active',
        activeStepKey: 'confirm',
        hasExecutionTimeline: false,
        hasProgressData: false,
      }).nextStepLabel,
    ).toBe('下一步：发布草稿并跟进学生完成情况');
  });

  it('completed and failed confirm labels use 发布', () => {
    const completed = buildAssignmentWorkflowIndicator({
      uploadJobId: 'job-1',
      uploadJobInfoStatus: 'confirmed',
      uploading: false,
      uploadConfirming: false,
      uploadDraft: null,
      uploadError: '',
      draftError: '',
      draftActionError: '',
    });
    expect(completed.label).toBe('已发布草稿');

    const confirming = buildAssignmentWorkflowIndicator({
      uploadJobId: 'job-1',
      uploadJobInfoStatus: 'confirming',
      uploading: false,
      uploadConfirming: true,
      uploadDraft: null,
      uploadError: '',
      draftError: '',
      draftActionError: '',
    });
    expect(confirming.label).toBe('发布中');

    const failed = buildAssignmentWorkflowIndicator({
      uploadJobId: 'job-1',
      uploadJobInfoStatus: 'confirming',
      uploading: false,
      uploadConfirming: true,
      uploadDraft: null,
      uploadError: '',
      draftError: '',
      draftActionError: 'boom',
    });
    expect(failed.label).toBe('发布失败');
  });
});
