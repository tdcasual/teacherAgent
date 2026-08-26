import { describe, expect, it } from 'vitest';
import {
  PENDING_CHAT_MAX_AGE_MS,
  parsePendingChatJob,
  parsePendingChatJobFromStorage,
} from './pendingChatJob';

const NOW_MS = 1_700_000_000_000;

const teacherJob = {
  job_id: 'job_teacher_1',
  request_id: 'req_teacher_1',
  placeholder_id: 'asst_teacher_1',
  user_text: '帮我出一份作业',
  session_id: 'sess_teacher_1',
  created_at: NOW_MS,
  lane_id: 'lane_a',
};

const studentJob = {
  job_id: 'job_student_1',
  request_id: 'req_student_1',
  placeholder_id: 'asst_student_1',
  user_text: '这道题怎么做',
  session_id: 'sess_student_1',
  created_at: NOW_MS,
};

describe('parsePendingChatJob (teacher)', () => {
  it('returns null for an expired teacher job older than 15 minutes', () => {
    const raw = JSON.stringify({
      ...teacherJob,
      created_at: NOW_MS - PENDING_CHAT_MAX_AGE_MS - 1,
    });
    expect(parsePendingChatJob(raw, NOW_MS)).toBeNull();
  });

  it('keeps a fresh teacher job including optional lane_id', () => {
    expect(parsePendingChatJob(JSON.stringify(teacherJob), NOW_MS)).toEqual(teacherJob);
  });

  it('keeps a teacher job at the exact 15 minute boundary', () => {
    const raw = JSON.stringify({
      ...teacherJob,
      created_at: NOW_MS - PENDING_CHAT_MAX_AGE_MS,
    });
    expect(parsePendingChatJob(raw, NOW_MS)?.job_id).toBe(teacherJob.job_id);
  });
});

describe('parsePendingChatJobFromStorage (student)', () => {
  it('still recovers a student job younger than 15 minutes', () => {
    const raw = JSON.stringify({
      ...studentJob,
      created_at: NOW_MS - PENDING_CHAT_MAX_AGE_MS + 1,
    });
    expect(parsePendingChatJobFromStorage(raw, NOW_MS)).toEqual({
      ...studentJob,
      created_at: NOW_MS - PENDING_CHAT_MAX_AGE_MS + 1,
    });
  });

  it('still discards a student job older than 15 minutes', () => {
    const raw = JSON.stringify({
      ...studentJob,
      created_at: NOW_MS - PENDING_CHAT_MAX_AGE_MS - 1,
    });
    expect(parsePendingChatJobFromStorage(raw, NOW_MS)).toBeNull();
  });

  it('still accepts student jobs with looser required fields', () => {
    const raw = JSON.stringify({
      job_id: 'job_loose',
      created_at: NOW_MS,
    });
    expect(parsePendingChatJobFromStorage(raw, NOW_MS)).toEqual({
      job_id: 'job_loose',
      request_id: '',
      placeholder_id: 'asst_recover_job_loose',
      user_text: '',
      session_id: '',
      created_at: NOW_MS,
    });
  });
});
