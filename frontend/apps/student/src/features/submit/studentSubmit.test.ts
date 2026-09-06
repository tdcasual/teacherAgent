import { describe, expect, it } from 'vitest'

import { matchReadyChatFiles, parseStudentSubmitResponse } from './studentSubmit'

describe('parseStudentSubmitResponse', () => {
  it('keeps HTTP 200 with submitted=false as a counted-failure, not a transport error', () => {
    const result = parseStudentSubmitResponse(
      {
        ok: true,
        submitted: false,
        assignment_id: 'HW_1',
        attempt_id: 'submission_empty',
        official_score: null,
        reason: 'min_graded_total',
      },
      200,
    )
    expect(result.ok).toBe(true)
    expect(result.submitted).toBe(false)
    expect(result.reason).toBe('min_graded_total')
    expect(result.official_score).toBeNull()
    expect(result.message).toContain('未记为提交')
  })

  it('reads official_score only when submitted is true', () => {
    const result = parseStudentSubmitResponse(
      {
        ok: true,
        submitted: true,
        assignment_id: 'HW_1',
        attempt_id: 'submission_ok',
        official_score: 8,
      },
      200,
    )
    expect(result.submitted).toBe(true)
    expect(result.official_score).toBe(8)
    expect(result.message).toContain('已提交')
  })

  it('treats non-2xx as an error even if the body says ok', () => {
    const result = parseStudentSubmitResponse({ ok: true, submitted: true }, 400)
    expect(result.ok).toBe(false)
    expect(result.submitted).toBe(false)
  })

  it('uses a distinct message when progress is unavailable', () => {
    const result = parseStudentSubmitResponse(
      {
        ok: true,
        submitted: false,
        assignment_id: 'HW_1',
        reason: 'progress_unavailable',
      },
      200,
    )
    expect(result.reason).toBe('progress_unavailable')
    expect(result.message).not.toContain('有效评分不足')
    expect(result.message).toContain('无法确认')
  })
})

describe('matchReadyChatFiles', () => {
  it('returns files only when every ready attachment has a matching blob', () => {
    const a = new File(['a'], 'a.pdf')
    const b = new File(['b'], 'b.pdf')
    expect(matchReadyChatFiles([{ fileName: 'a.pdf' }, { fileName: 'b.pdf' }], [a, b])).toEqual([a, b])
  })

  it('returns empty when restored names have no File blobs', () => {
    expect(matchReadyChatFiles([{ fileName: 'restored.pdf' }], [])).toEqual([])
  })

  it('does not include extra unmatched blobs', () => {
    const ready = new File(['ok'], 'ok.pdf')
    const extra = new File(['bad'], 'bad.exe')
    expect(matchReadyChatFiles([{ fileName: 'ok.pdf' }], [extra, ready])).toEqual([ready])
  })
})
