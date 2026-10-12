import { describe, expect, it } from 'vitest';
import { formatUploadJobStatus } from './workbenchFormatters';

describe('workbenchFormatters publish-draft copy', () => {
  it('maps confirmed/created job status to 已发布草稿', () => {
    expect(formatUploadJobStatus({ job_id: 'job-1', status: 'confirmed' })).toContain('已发布草稿');
    expect(formatUploadJobStatus({ job_id: 'job-1', status: 'created' })).toContain('已发布草稿');
  });
});
