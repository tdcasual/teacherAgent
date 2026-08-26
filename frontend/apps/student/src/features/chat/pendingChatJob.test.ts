import { describe, expect, it } from 'vitest'
import { PENDING_CHAT_MAX_AGE_MS, parsePendingChatJobFromStorage } from './pendingChatJob'

const NOW_MS = 1_700_000_000_000

describe('student pendingChatJob re-export', () => {
  it('still recovers a job younger than 15 minutes', () => {
    const createdAt = NOW_MS - PENDING_CHAT_MAX_AGE_MS + 1
    const parsed = parsePendingChatJobFromStorage(
      JSON.stringify({
        job_id: 'job_student_fresh',
        request_id: 'req_1',
        placeholder_id: 'asst_1',
        user_text: 'hello',
        session_id: 'sess_1',
        created_at: createdAt,
      }),
      NOW_MS,
    )
    expect(parsed?.job_id).toBe('job_student_fresh')
  })

  it('still discards a job older than 15 minutes', () => {
    const parsed = parsePendingChatJobFromStorage(
      JSON.stringify({
        job_id: 'job_student_stale',
        request_id: 'req_1',
        placeholder_id: 'asst_1',
        user_text: 'hello',
        session_id: 'sess_1',
        created_at: NOW_MS - PENDING_CHAT_MAX_AGE_MS - 1,
      }),
      NOW_MS,
    )
    expect(parsed).toBeNull()
  })
})
