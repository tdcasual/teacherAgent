import { expect, test } from '@playwright/test'
import { openTeacherApp, setupBasicTeacherApiMocks, setupTeacherState } from './helpers/teacherHarness'

const fakePdfFile = {
  name: 'paper.pdf',
  mimeType: 'application/pdf',
  buffer: Buffer.from('%PDF-1.4 exam-paper'),
}

const fakeXlsxFile = {
  name: 'scores.xlsx',
  mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  buffer: Buffer.from('xlsx-sample'),
}

const buildExamDraft = (jobId: string, examId: string) => ({
  job_id: jobId,
  exam_id: examId,
  meta: {
    date: '2026-02-08',
    class_name: '高二2403班',
  },
  date: '2026-02-08',
  questions: [
    { question_id: 'Q1', question_no: '1', max_score: 4 },
    { question_id: 'Q2', question_no: '2', max_score: 6 },
  ],
  score_schema: {},
  answer_key_text: '',
  answer_text_excerpt: '1 A\n2 C',
  counts: { students: 2, questions: 2 },
  scoring: {
    status: 'partial',
    students_total: 2,
    students_scored: 1,
    default_max_score_qids: ['Q2', 'Q5'],
  },
  totals_summary: {
    avg_total: 71,
    median_total: 72,
    max_total_observed: 90,
  },
})

test('exam draft shows default max-score warning when scoring fallback exists', async ({ page }) => {
  const jobId = 'job_exam_system_warning_1'

  await setupTeacherState(page, {
    stateOverrides: {
      teacherWorkbenchTab: 'workflow',
      teacherActiveUpload: JSON.stringify({ type: 'exam', job_id: jobId }),
    },
  })
  await setupBasicTeacherApiMocks(page)

  await page.route('http://localhost:8000/exam/upload/status**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        job_id: jobId,
        status: 'done',
        progress: 100,
        exam_id: 'EX-SYS-001',
      }),
    })
  })

  await page.route('http://localhost:8000/exam/upload/draft**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, draft: buildExamDraft(jobId, 'EX-SYS-001') }),
    })
  })

  await page.goto('/')

  await expect(page.locator('#workflow-exam-draft-section')).toContainText('提示：有 2 题缺少满分')
})

test('exam answer excerpt helper fills answer textarea', async ({ page }) => {
  const jobId = 'job_exam_system_excerpt_1'

  await setupTeacherState(page, {
    stateOverrides: {
      teacherWorkbenchTab: 'workflow',
      teacherActiveUpload: JSON.stringify({ type: 'exam', job_id: jobId }),
    },
  })
  await setupBasicTeacherApiMocks(page)

  await page.route('http://localhost:8000/exam/upload/status**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ job_id: jobId, status: 'done', progress: 100, exam_id: 'EX-SYS-002' }),
    })
  })

  await page.route('http://localhost:8000/exam/upload/draft**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, draft: buildExamDraft(jobId, 'EX-SYS-002') }),
    })
  })

  await page.goto('/')

  const examSection = page.locator('#workflow-exam-draft-section')
  await examSection.getByText('查看识别到的答案文本（可用作填充参考）').click()
  await examSection.getByRole('button', { name: '用识别文本填充' }).click()

  const answerTextarea = examSection.locator('textarea').first()
  await expect(answerTextarea).toHaveValue('1 A\n2 C')
})

test('saving exam draft sends edited meta and answer key payload', async ({ page }) => {
  const jobId = 'job_exam_system_save_1'
  let capturedBody: any = null

  await setupTeacherState(page, {
    stateOverrides: {
      teacherWorkbenchTab: 'workflow',
      teacherActiveUpload: JSON.stringify({ type: 'exam', job_id: jobId }),
    },
  })
  await setupBasicTeacherApiMocks(page)

  await page.route('http://localhost:8000/exam/upload/status**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ job_id: jobId, status: 'done', progress: 100, exam_id: 'EX-SYS-003' }),
    })
  })

  await page.route('http://localhost:8000/exam/upload/draft**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, draft: buildExamDraft(jobId, 'EX-SYS-003') }),
    })
  })

  await page.route('http://localhost:8000/exam/upload/draft/save', async (route) => {
    capturedBody = JSON.parse(route.request().postData() || '{}')
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, message: '考试草稿已保存。', draft_version: 2 }),
    })
  })

  await page.goto('/')

  const examSection = page.locator('#workflow-exam-draft-section')
  const metaCard = examSection.locator('.draft-card').first()
  const answerTextarea = examSection.locator('textarea').first()

  await metaCard.locator('input').nth(0).fill('2026-02-10')
  await metaCard.locator('input').nth(1).fill('高二2404班')
  await answerTextarea.fill('1 B\n2 D')

  await examSection.getByRole('button', { name: '保存草稿' }).click()

  await expect.poll(() => capturedBody).not.toBeNull()
  expect(capturedBody.meta.date).toBe('2026-02-10')
  expect(capturedBody.meta.class_name).toBe('高二2404班')
  expect(capturedBody.answer_key_text).toBe('1 B\n2 D')
})

test('exam confirm job_not_ready error is surfaced with progress hint', async ({ page }) => {
  const jobId = 'job_exam_system_not_ready_1'

  await setupTeacherState(page, {
    stateOverrides: {
      teacherWorkbenchTab: 'workflow',
      teacherActiveUpload: JSON.stringify({ type: 'exam', job_id: jobId }),
    },
  })
  await setupBasicTeacherApiMocks(page)

  await page.route('http://localhost:8000/exam/upload/status**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ job_id: jobId, status: 'done', progress: 100, exam_id: 'EX-SYS-004' }),
    })
  })

  await page.route('http://localhost:8000/exam/upload/draft**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, draft: buildExamDraft(jobId, 'EX-SYS-004') }),
    })
  })

  await page.route('http://localhost:8000/exam/upload/draft/save', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, message: '考试草稿已保存。' }),
    })
  })

  await page.route('http://localhost:8000/exam/upload/confirm', async (route) => {
    await route.fulfill({
      status: 409,
      contentType: 'application/json',
      body: JSON.stringify({
        detail: {
          error: 'job_not_ready',
          message: '解析尚未完成',
          progress: 72,
        },
      }),
    })
  })

  await page.goto('/')

  const examSection = page.locator('#workflow-exam-draft-section')
  await examSection.getByRole('button', { name: '创建考试' }).click()

  await expect(examSection.getByText('解析尚未完成（进度 72%）')).toBeVisible()
})

test('exam upload start uses updated API base from settings', async ({ page }) => {
  let customBaseUploadCalls = 0

  await openTeacherApp(page, {
    stateOverrides: {
      teacherWorkbenchTab: 'workflow',
    },
  })

  await page.route('http://127.0.0.1:9101/**', async (route) => {
    const { pathname } = new URL(route.request().url())
    if (pathname === '/exam/upload/start') {
      customBaseUploadCalls += 1
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, job_id: 'job_custom_base_exam' }),
      })
      return
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
  })

  await page.getByRole('button', { name: '考试', exact: true }).first().click()
  await page.getByRole('button', { name: '设置' }).click()
  await page.getByPlaceholder('http://localhost:8000').fill('http://127.0.0.1:9101')

  await page.locator('#workflow-upload-section input[type="file"]').nth(0).setInputFiles(fakePdfFile)
  await page.locator('#workflow-upload-section input[type="file"]').nth(2).setInputFiles(fakeXlsxFile)
  await page.locator('#workflow-upload-section form.upload-form button[type="submit"]').click()

  await expect.poll(() => customBaseUploadCalls).toBe(1)
})
