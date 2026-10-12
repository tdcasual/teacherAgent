import { describe, expect, it } from 'vitest';
import {
  formatDraftSummary,
  formatUploadJobStatus,
  formatUploadJobSummary,
} from './workbenchFormatters';

describe('workbenchFormatters publish-draft copy', () => {
  it('maps confirmed/created job status to 已发布草稿', () => {
    expect(formatUploadJobStatus({ job_id: 'job-1', status: 'confirmed' })).toContain('已发布草稿');
    expect(formatUploadJobStatus({ job_id: 'job-1', status: 'created' })).toContain('已发布草稿');
  });

  it('collapsed summaries use 已发布 / 待发布', () => {
    expect(formatUploadJobSummary({ job_id: 'job-1', status: 'confirmed' })).toContain('已发布');
    expect(formatUploadJobSummary({ job_id: 'job-1', status: 'created' })).toContain('已发布');
    expect(formatUploadJobSummary({ job_id: 'job-1', status: 'confirmed' })).not.toContain('已创建');
    const draft = {
      assignment_id: 'HW1',
      date: '2026-10-10',
      scope: 'class' as const,
      questions: [],
      requirements: {},
    };
    expect(formatDraftSummary(draft, { job_id: 'job-1', status: 'confirmed' })).toContain('已发布');
    expect(formatDraftSummary(draft, { job_id: 'job-1', status: 'done' })).toContain('待发布');
    expect(formatDraftSummary(draft, { job_id: 'job-1', status: 'done' })).not.toContain('待创建');
  });
});
