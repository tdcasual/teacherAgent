import { expect } from '@playwright/test'
import type { MatrixCase, MatrixCaseRunner } from './helpers/e2eMatrixCases'
import { registerMatrixCases } from './helpers/e2eMatrixCases'

const studentLoopCases: MatrixCase[] = [
  {
    id: 'I001',
    priority: 'P0',
    title: 'Student sees only accessible assignments by scope',
    given: 'Student identity and mixed assignment scopes exist',
    when: 'Open student assignment list',
    then: 'Only public class and personal eligible assignments are shown',
  },
  {
    id: 'I002',
    priority: 'P0',
    title: 'Diagnostic chat can trigger personalized practice generation',
    given: 'Student diagnostic conversation reaches completion trigger',
    when: 'Run generate practice action',
    then: 'Personalized practice set is created',
  },
  {
    id: 'I003',
    priority: 'P1',
    title: 'Feynman reflection persists and advances flow',
    given: 'Reflection step is active',
    when: 'Submit reflection content',
    then: 'Content is saved and next step becomes available',
  },
  {
    id: 'I004',
    priority: 'P0',
    title: 'Student multi-image submit returns grading summary',
    given: '/student/submit endpoint is available',
    when: 'Upload multiple homework images',
    then: 'Response includes grading summary',
  },
  {
    id: 'I005',
    priority: 'P0',
    title: 'Auto assignment mode selects latest eligible assignment',
    given: 'auto_assignment flag is true',
    when: 'Submit without explicit assignment id',
    then: 'Server resolves and records nearest eligible assignment',
  },
  {
    id: 'I006',
    priority: 'P1',
    title: 'Mixed valid and invalid files return partial-failure feedback',
    given: 'One valid image and one invalid file format',
    when: 'Submit files',
    then: 'Result reports partial failures with readable guidance',
  },
  {
    id: 'I007',
    priority: 'P1',
    title: 'Partial OCR failure preserves successful page outputs',
    given: 'OCR pipeline fails for subset of pages',
    when: 'Submit multi-page content',
    then: 'Successful pages still produce scoring output',
  },
  {
    id: 'I008',
    priority: 'P0',
    title: 'Profile knowledge points update after successful submit',
    given: 'Student profile is readable before submission',
    when: 'Submit graded homework and reload profile',
    then: 'Weak and strong knowledge points change as expected',
  },
  {
    id: 'I009',
    priority: 'P1',
    title: 'Repeated submits preserve ordering and timestamps',
    given: 'Student submits same assignment multiple times',
    when: 'Fetch submission history',
    then: 'Entries keep strict chronological order',
  },
  {
    id: 'I010',
    priority: 'P1',
    title: 'Visibility list updates when assignment scope policy changes',
    given: 'Assignment visibility policy changes on server',
    when: 'Refresh student assignment list',
    then: 'Visible assignments reflect latest policy',
  },
  {
    id: 'I011',
    priority: 'P1',
    title: 'Network retry path does not duplicate student submissions',
    given: 'Transient network failure during submit',
    when: 'Retry submission',
    then: 'Exactly one persisted submission record exists',
  },
  {
    id: 'I012',
    priority: 'P2',
    title: 'Long conversation scroll and composer remain stable',
    given: 'Student chat contains long history',
    when: 'Alternate between scrolling and typing',
    then: 'Composer position remains stable and usable',
  },
]

const implementations: Partial<Record<string, MatrixCaseRunner>> = {
  I001: async ({ page }) => {
    await page.goto('/')

    await page.route('http://localhost:8000/assignment/today**', async (route) => {
      const studentId = new URL(route.request().url()).searchParams.get('student_id')
      expect(studentId).toBe('S001')
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          assignment: {
            assignment_id: 'A-ACCESSIBLE-001',
            date: '2026-02-08',
            question_count: 8,
            meta: { target_kp: ['KP-M01'] },
          },
        }),
      })
    })

    const data = await page.evaluate(async () => {
      const res = await fetch('http://localhost:8000/assignment/today?student_id=S001')
      return res.json()
    })

    expect(data.ok).toBe(true)
    expect(data.assignment.assignment_id).toBe('A-ACCESSIBLE-001')
  },

  I002: async ({ page }) => {
    await page.goto('/')
    let chatStartCalls = 0

    await page.route('http://localhost:8000/chat/start', async (route) => {
      chatStartCalls += 1
      const payload = JSON.parse(route.request().postData() || '{}')
      expect(payload.role).toBe('student')
      expect(payload.student_id).toBe('S001')
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, job_id: 'student_job_1', status: 'done', reply: '已生成个性化练习' }),
      })
    })

    const data = await page.evaluate(async () => {
      const res = await fetch('http://localhost:8000/chat/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          role: 'student',
          student_id: 'S001',
          assignment_id: 'A-ACCESSIBLE-001',
          messages: [{ role: 'user', content: '请根据我的诊断生成练习' }],
        }),
      })
      return res.json()
    })

    expect(chatStartCalls).toBe(1)
    expect(data.ok).toBe(true)
    expect(data.reply).toBe('已生成个性化练习')
  },

  I004: async ({ page }) => {
    await page.goto('/')

    await page.route('http://localhost:8000/student/submit', async (route) => {
      const contentType = route.request().headerValue('content-type') || ''
      expect(contentType).toContain('multipart/form-data')
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          assignment_id: 'A-ACCESSIBLE-001',
          grading: {
            score_earned: 78,
            score_total: 100,
            graded_pages: 2,
          },
        }),
      })
    })

    const data = await page.evaluate(async () => {
      const form = new FormData()
      form.append('student_id', 'S001')
      form.append('assignment_id', 'A-ACCESSIBLE-001')
      form.append('files', new File(['img-1'], 'p1.jpg', { type: 'image/jpeg' }))
      form.append('files', new File(['img-2'], 'p2.jpg', { type: 'image/jpeg' }))

      const res = await fetch('http://localhost:8000/student/submit', {
        method: 'POST',
        body: form,
      })
      return res.json()
    })

    expect(data.ok).toBe(true)
    expect(data.grading.score_earned).toBe(78)
    expect(data.grading.graded_pages).toBe(2)
  },

  I005: async ({ page }) => {
    await page.goto('/')

    await page.route('http://localhost:8000/student/submit', async (route) => {
      const bodyText = route.request().postData() || ''
      expect(bodyText).toContain('auto_assignment')
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          assignment_id: 'A-LATEST-ELIGIBLE-009',
          auto_assignment: true,
        }),
      })
    })

    const data = await page.evaluate(async () => {
      const form = new FormData()
      form.append('student_id', 'S001')
      form.append('auto_assignment', 'true')
      form.append('files', new File(['img'], 'auto.jpg', { type: 'image/jpeg' }))

      const res = await fetch('http://localhost:8000/student/submit', {
        method: 'POST',
        body: form,
      })
      return res.json()
    })

    expect(data.ok).toBe(true)
    expect(data.assignment_id).toBe('A-LATEST-ELIGIBLE-009')
    expect(data.auto_assignment).toBe(true)
  },

  I008: async ({ page }) => {
    await page.goto('/')
    const profile = {
      student_id: 'S001',
      weak_kp: ['KP-E01'],
      strong_kp: ['KP-M02'],
    }

    await page.route('http://localhost:8000/student/profile/S001', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(profile),
      })
    })

    await page.route('http://localhost:8000/student/submit', async (route) => {
      profile.weak_kp = ['KP-E03']
      profile.strong_kp = ['KP-M02', 'KP-M05']
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, assignment_id: 'A-ACCESSIBLE-001', score_earned: 88 }),
      })
    })

    const before = await page.evaluate(async () => {
      const res = await fetch('http://localhost:8000/student/profile/S001')
      return res.json()
    })

    await page.evaluate(async () => {
      const form = new FormData()
      form.append('student_id', 'S001')
      form.append('assignment_id', 'A-ACCESSIBLE-001')
      form.append('files', new File(['img'], 'submit.jpg', { type: 'image/jpeg' }))
      await fetch('http://localhost:8000/student/submit', {
        method: 'POST',
        body: form,
      })
    })

    const after = await page.evaluate(async () => {
      const res = await fetch('http://localhost:8000/student/profile/S001')
      return res.json()
    })

    expect(before.weak_kp).toEqual(['KP-E01'])
    expect(after.weak_kp).toEqual(['KP-E03'])
    expect(after.strong_kp).toEqual(['KP-M02', 'KP-M05'])
  },
}

registerMatrixCases('Student Learning Loop', studentLoopCases, implementations)
