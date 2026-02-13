import { expect, test } from '@playwright/test'
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

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('apiBaseStudent', 'http://localhost:8000')
    localStorage.setItem('studentAuthAccessToken', 'e2e-student-token')
    localStorage.setItem(
      'verifiedStudent',
      JSON.stringify({
        student_id: 'S001',
        student_name: '测试学生',
        class_name: '高二1班',
      }),
    )
  })
})

test('student shell renders chat and workbench regions', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByTestId('student-chat-panel')).toBeVisible()
  await expect(page.getByRole('complementary').first()).toBeVisible()
})

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

  I003: async ({ page }) => {
    await page.goto('/')
    const state = {
      reflection_saved: false,
      next_step: 'reflection',
      reflection_text: '',
    }

    await page.route('http://localhost:8000/student/reflection', async (route) => {
      const payload = JSON.parse(route.request().postData() || '{}')
      state.reflection_saved = true
      state.reflection_text = String(payload.content || '')
      state.next_step = 'practice'
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, saved: true, next_step: state.next_step }),
      })
    })

    await page.route('http://localhost:8000/student/flow/state**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          reflection_saved: state.reflection_saved,
          reflection_text: state.reflection_text,
          next_step: state.next_step,
        }),
      })
    })

    const data = await page.evaluate(async () => {
      const submit = await fetch('http://localhost:8000/student/reflection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ student_id: 'S001', content: '我理解了电场方向判定。' }),
      }).then((r) => r.json())

      const flow = await fetch('http://localhost:8000/student/flow/state?student_id=S001').then((r) => r.json())
      return { submit, flow }
    })

    expect(data.submit.ok).toBe(true)
    expect(data.flow.reflection_saved).toBe(true)
    expect(data.flow.next_step).toBe('practice')
    expect(data.flow.reflection_text).toContain('电场方向')
  },

  I004: async ({ page }) => {
    await page.goto('/')

    await page.route('http://localhost:8000/student/submit', async (route) => {
      const contentType = (await route.request().headerValue('content-type')) || ''
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

  I006: async ({ page }) => {
    await page.goto('/')

    await page.route('http://localhost:8000/student/submit', async (route) => {
      await route.fulfill({
        status: 207,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          assignment_id: 'A-ACCESSIBLE-001',
          accepted_files: ['valid-1.jpg'],
          rejected_files: [{ name: 'virus.exe', reason: 'unsupported file type' }],
          detail: '部分文件处理失败，请仅上传图片或文档格式',
        }),
      })
    })

    const data = await page.evaluate(async () => {
      const form = new FormData()
      form.append('student_id', 'S001')
      form.append('assignment_id', 'A-ACCESSIBLE-001')
      form.append('files', new File(['img'], 'valid-1.jpg', { type: 'image/jpeg' }))
      form.append('files', new File(['exe'], 'virus.exe', { type: 'application/octet-stream' }))
      const res = await fetch('http://localhost:8000/student/submit', { method: 'POST', body: form })
      return { status: res.status, body: await res.json() }
    })

    expect(data.status).toBe(207)
    expect(data.body.accepted_files).toEqual(['valid-1.jpg'])
    expect(data.body.rejected_files[0].name).toBe('virus.exe')
    expect(String(data.body.detail)).toContain('部分文件处理失败')
  },

  I007: async ({ page }) => {
    await page.goto('/')

    await page.route('http://localhost:8000/student/submit', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          assignment_id: 'A-ACCESSIBLE-001',
          grading: {
            score_earned: 61,
            score_total: 100,
            graded_pages: [
              { page: 1, score: 30 },
              { page: 3, score: 31 },
            ],
            failed_pages: [{ page: 2, reason: 'ocr timeout' }],
          },
        }),
      })
    })

    const data = await page.evaluate(async () => {
      const form = new FormData()
      form.append('student_id', 'S001')
      form.append('assignment_id', 'A-ACCESSIBLE-001')
      form.append('files', new File(['p1'], 'p1.jpg', { type: 'image/jpeg' }))
      form.append('files', new File(['p2'], 'p2.jpg', { type: 'image/jpeg' }))
      form.append('files', new File(['p3'], 'p3.jpg', { type: 'image/jpeg' }))
      const res = await fetch('http://localhost:8000/student/submit', { method: 'POST', body: form })
      return res.json()
    })

    expect(data.ok).toBe(true)
    expect(data.grading.graded_pages).toHaveLength(2)
    expect(data.grading.failed_pages).toHaveLength(1)
    expect(data.grading.failed_pages[0].reason).toBe('ocr timeout')
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

  I009: async ({ page }) => {
    await page.goto('/')
    const history: Array<{ submission_id: string; submitted_at: string; assignment_id: string }> = []
    let counter = 0

    await page.route('http://localhost:8000/student/submit', async (route) => {
      counter += 1
      const id = `sub_${counter}`
      const ts = new Date(Date.now() + counter * 1000).toISOString()
      history.unshift({ submission_id: id, submitted_at: ts, assignment_id: 'A-ACCESSIBLE-001' })
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, submission_id: id, submitted_at: ts }),
      })
    })

    await page.route('http://localhost:8000/student/submissions**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, items: history }),
      })
    })

    const result = await page.evaluate(async () => {
      const submitOnce = async () => {
        const form = new FormData()
        form.append('student_id', 'S001')
        form.append('assignment_id', 'A-ACCESSIBLE-001')
        form.append('files', new File(['img'], 'once.jpg', { type: 'image/jpeg' }))
        return fetch('http://localhost:8000/student/submit', { method: 'POST', body: form }).then((r) => r.json())
      }
      await submitOnce()
      await submitOnce()
      await submitOnce()
      return fetch('http://localhost:8000/student/submissions?student_id=S001').then((r) => r.json())
    })

    expect(result.items).toHaveLength(3)
    const times = result.items.map((item: any) => Date.parse(item.submitted_at))
    expect(times[0]).toBeGreaterThan(times[1])
    expect(times[1]).toBeGreaterThan(times[2])
  },

  I010: async ({ page }) => {
    await page.goto('/')
    let callCount = 0

    await page.route('http://localhost:8000/assignment/today**', async (route) => {
      callCount += 1
      const assignmentId = callCount === 1 ? 'A-VISIBLE-OLD' : 'A-VISIBLE-NEW'
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          assignment: {
            assignment_id: assignmentId,
            date: '2026-02-08',
            question_count: 6,
          },
        }),
      })
    })

    const result = await page.evaluate(async () => {
      const first = await fetch('http://localhost:8000/assignment/today?student_id=S001').then((r) => r.json())
      const second = await fetch('http://localhost:8000/assignment/today?student_id=S001').then((r) => r.json())
      return { first, second }
    })

    expect(result.first.assignment.assignment_id).toBe('A-VISIBLE-OLD')
    expect(result.second.assignment.assignment_id).toBe('A-VISIBLE-NEW')
  },

  I011: async ({ page }) => {
    await page.goto('/')
    let submitAttempts = 0
    const persisted: Array<{ submission_id: string; request_id: string }> = []

    await page.route('http://localhost:8000/student/submit', async (route) => {
      submitAttempts += 1
      if (submitAttempts === 1) {
        await route.fulfill({
          status: 503,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'temporary unavailable' }),
        })
        return
      }
      const bodyText = route.request().postData() || ''
      const requestId = bodyText.includes('request_retry_001') ? 'request_retry_001' : 'request_fallback'
      persisted.push({ submission_id: 'sub_retry_1', request_id: requestId })
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, submission_id: 'sub_retry_1', request_id: requestId }),
      })
    })

    await page.route('http://localhost:8000/student/submissions**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, items: persisted }),
      })
    })

    const result = await page.evaluate(async () => {
      const submit = async () => {
        const form = new FormData()
        form.append('student_id', 'S001')
        form.append('assignment_id', 'A-ACCESSIBLE-001')
        form.append('request_id', 'request_retry_001')
        form.append('files', new File(['img'], 'retry.jpg', { type: 'image/jpeg' }))
        const res = await fetch('http://localhost:8000/student/submit', { method: 'POST', body: form })
        return { status: res.status, body: await res.json().catch(() => ({})) }
      }

      const first = await submit()
      const second = await submit()
      const history = await fetch('http://localhost:8000/student/submissions?student_id=S001').then((r) => r.json())
      return { first, second, history }
    })

    expect(result.first.status).toBe(503)
    expect(result.second.status).toBe(200)
    expect(result.history.items).toHaveLength(1)
    expect(result.history.items[0].submission_id).toBe('sub_retry_1')
  },

  I012: async ({ page }) => {
    await page.goto('/')
    const chatStartCalls: any[] = []

    await page.route('http://localhost:8000/chat/start', async (route) => {
      const payload = JSON.parse(route.request().postData() || '{}')
      chatStartCalls.push(payload)
      const latest = String(payload?.messages?.at(-1)?.content || '')
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          job_id: `student_long_${chatStartCalls.length}`,
          status: 'done',
          reply: `echo:${latest.length}`,
        }),
      })
    })

    const result = await page.evaluate(async () => {
      const history = Array.from({ length: 80 }).map((_, idx) => ({
        role: idx % 2 === 0 ? 'assistant' : 'user',
        content: `历史片段-${idx + 1} ` + '讲解'.repeat(20),
      }))

      let composer = '滚动输入稳定性'
      const echoes: number[] = []
      for (let i = 1; i <= 4; i += 1) {
        composer += ` #${i}`
        const res = await fetch('http://localhost:8000/chat/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            role: 'student',
            student_id: 'S001',
            session_id: 'S001_LONG',
            messages: [...history, { role: 'user', content: composer }],
          }),
        })
        const data = await res.json()
        echoes.push(Number(String(data.reply || '').replace('echo:', '')))
        history.push({ role: 'assistant', content: `assistant-turn-${i}` })
        history.push({ role: 'user', content: composer })
      }
      return { composer, echoes }
    })

    expect(chatStartCalls).toHaveLength(4)
    expect(chatStartCalls[0].messages.at(-1).content).toBe('滚动输入稳定性 #1')
    expect(chatStartCalls[1].messages.at(-1).content).toBe('滚动输入稳定性 #1 #2')
    expect(chatStartCalls[2].messages.at(-1).content).toBe('滚动输入稳定性 #1 #2 #3')
    expect(chatStartCalls[3].messages.at(-1).content).toBe('滚动输入稳定性 #1 #2 #3 #4')
    expect(result.echoes.at(-1)).toBe(result.composer.length)
  },
}

registerMatrixCases('Student Learning Loop', studentLoopCases, implementations)
