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
  await page.getByRole('button', { name: '关闭' }).click()

  await page.locator('#workflow-upload-section input[type="file"]').nth(0).setInputFiles(fakePdfFile)
  await page.locator('#workflow-upload-section input[type="file"]').nth(2).setInputFiles(fakeXlsxFile)
  await page.locator('#workflow-upload-section form.upload-form button[type="submit"]').click()

  await expect.poll(() => customBaseUploadCalls).toBe(1)
})

test('exam confirm success sets terminal button text and clears active marker', async ({ page }) => {
  const jobId = 'job_exam_system_confirm_success_1'

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
      body: JSON.stringify({ job_id: jobId, status: 'done', progress: 100, exam_id: 'EX-SYS-CONFIRM-001' }),
    })
  })

  await page.route('http://localhost:8000/exam/upload/draft**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, draft: buildExamDraft(jobId, 'EX-SYS-CONFIRM-001') }),
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
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        message: '考试已确认创建。',
        exam_id: 'EX-SYS-CONFIRM-001',
      }),
    })
  })

  await page.goto('/')
  const examSection = page.locator('#workflow-exam-draft-section')
  await examSection.getByRole('button', { name: '创建考试' }).click()

  await expect(examSection.getByRole('button', { name: '已创建' })).toBeVisible()
  await expect
    .poll(async () => page.evaluate(() => localStorage.getItem('teacherActiveUpload')))
    .toBeNull()
})

test('exam draft save failure is surfaced as workflow error', async ({ page }) => {
  const jobId = 'job_exam_system_save_fail_1'

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
      body: JSON.stringify({ job_id: jobId, status: 'done', progress: 100, exam_id: 'EX-SYS-SAVEFAIL-001' }),
    })
  })

  await page.route('http://localhost:8000/exam/upload/draft**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, draft: buildExamDraft(jobId, 'EX-SYS-SAVEFAIL-001') }),
    })
  })

  await page.route('http://localhost:8000/exam/upload/draft/save', async (route) => {
    await route.fulfill({
      status: 500,
      contentType: 'text/plain',
      body: 'exam draft save failed',
    })
  })

  await page.goto('/')

  const examSection = page.locator('#workflow-exam-draft-section')
  await examSection.getByRole('button', { name: '保存草稿' }).click()
  await expect(examSection.getByText('exam draft save failed')).toBeVisible()
})

test('exam draft without answer excerpt shows fallback hint text', async ({ page }) => {
  const jobId = 'job_exam_system_no_excerpt_1'

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
      body: JSON.stringify({ job_id: jobId, status: 'done', progress: 100, exam_id: 'EX-SYS-NOEXCERPT-001' }),
    })
  })

  await page.route('http://localhost:8000/exam/upload/draft**', async (route) => {
    const draft = buildExamDraft(jobId, 'EX-SYS-NOEXCERPT-001')
    draft.answer_text_excerpt = ''
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, draft }),
    })
  })

  await page.goto('/')

  await expect(page.locator('#workflow-exam-draft-section')).toContainText(
    '未检测到答案文件识别文本。你也可以直接粘贴答案文本。',
  )
})

test('exam scoring unscored status renders localized label', async ({ page }) => {
  const jobId = 'job_exam_system_unscored_1'

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
      body: JSON.stringify({ job_id: jobId, status: 'done', progress: 100, exam_id: 'EX-SYS-UNSCORED-001' }),
    })
  })

  await page.route('http://localhost:8000/exam/upload/draft**', async (route) => {
    const draft = buildExamDraft(jobId, 'EX-SYS-UNSCORED-001')
    draft.scoring.status = 'unscored'
    draft.scoring.students_scored = 0
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, draft }),
    })
  })

  await page.goto('/')
  await expect(page.locator('#workflow-exam-draft-section')).toContainText('评分状态：未评分')
})

test('exam confirm server error keeps create button available for retry', async ({ page }) => {
  const jobId = 'job_exam_system_confirm_fail_1'

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
      body: JSON.stringify({ job_id: jobId, status: 'done', progress: 100, exam_id: 'EX-SYS-CONFIRMFAIL-001' }),
    })
  })

  await page.route('http://localhost:8000/exam/upload/draft**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, draft: buildExamDraft(jobId, 'EX-SYS-CONFIRMFAIL-001') }),
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
      status: 500,
      contentType: 'text/plain',
      body: 'confirm exam failed',
    })
  })

  await page.goto('/')

  const examSection = page.locator('#workflow-exam-draft-section')
  await examSection.getByRole('button', { name: '创建考试' }).click()
  await expect(examSection.getByText('confirm exam failed')).toBeVisible()
  await expect(examSection.getByRole('button', { name: '创建考试' })).toBeVisible()
})

test('custom exam API base is persisted to localStorage', async ({ page }) => {
  await openTeacherApp(page, {
    stateOverrides: {
      teacherWorkbenchTab: 'workflow',
    },
  })

  await page.getByRole('button', { name: '设置' }).click()
  await page.getByPlaceholder('http://localhost:8000').fill('http://127.0.0.1:9494')
  await page.getByRole('button', { name: '关闭' }).click()

  await expect
    .poll(async () => page.evaluate(() => localStorage.getItem('apiBaseTeacher')))
    .toBe('http://127.0.0.1:9494')
})

test('exam failed status clears active upload marker', async ({ page }) => {
  const jobId = 'job_exam_system_failed_1'

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
        status: 'failed',
        error: 'exam parse failed',
      }),
    })
  })

  await page.goto('/')
  await expect
    .poll(async () => page.evaluate(() => localStorage.getItem('teacherActiveUpload')))
    .toBeNull()
})

test('exam draft load failure is surfaced in workflow panel', async ({ page }) => {
  const jobId = 'job_exam_system_draft_load_fail_1'

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
      body: JSON.stringify({ job_id: jobId, status: 'done', progress: 100, exam_id: 'EX-SYS-DRAFTFAIL-001' }),
    })
  })

  await page.route('http://localhost:8000/exam/upload/draft**', async (route) => {
    await route.fulfill({
      status: 500,
      contentType: 'text/plain',
      body: 'exam draft load failed',
    })
  })

  await page.goto('/')
  await expect(page.getByText('exam draft load failed')).toBeVisible()
})

test('exam draft payload without questions is rejected with explicit error', async ({ page }) => {
  const jobId = 'job_exam_system_draft_missing_questions_1'

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
      body: JSON.stringify({ job_id: jobId, status: 'done', progress: 100, exam_id: 'EX-SYS-DRAFTMISS-001' }),
    })
  })

  await page.route('http://localhost:8000/exam/upload/draft**', async (route) => {
    const draft = buildExamDraft(jobId, 'EX-SYS-DRAFTMISS-001') as any
    delete draft.questions
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, draft }),
    })
  })

  await page.goto('/')
  await expect(page.getByText('draft 数据缺失')).toBeVisible()
})

test('exam confirm request payload includes job_id', async ({ page }) => {
  const jobId = 'job_exam_system_confirm_payload_1'
  let capturedConfirmBody: any = null

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
      body: JSON.stringify({ job_id: jobId, status: 'done', progress: 100, exam_id: 'EX-SYS-PAYLOAD-001' }),
    })
  })

  await page.route('http://localhost:8000/exam/upload/draft**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, draft: buildExamDraft(jobId, 'EX-SYS-PAYLOAD-001') }),
    })
  })

  await page.route('http://localhost:8000/exam/upload/draft/save', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
  })

  await page.route('http://localhost:8000/exam/upload/confirm', async (route) => {
    capturedConfirmBody = JSON.parse(route.request().postData() || '{}')
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, exam_id: 'EX-SYS-PAYLOAD-001', message: '考试已确认创建。' }),
    })
  })

  await page.goto('/')
  await page.locator('#workflow-exam-draft-section').getByRole('button', { name: '创建考试' }).click()

  await expect.poll(() => capturedConfirmBody).not.toBeNull()
  expect(capturedConfirmBody.job_id).toBe(jobId)
})

test('exam upload validates missing paper file before request', async ({ page }) => {
  await openTeacherApp(page, {
    stateOverrides: {
      teacherWorkbenchTab: 'workflow',
    },
  })

  await page.getByRole('button', { name: '考试', exact: true }).first().click()
  await page.locator('#workflow-upload-section input[type="file"]').nth(2).setInputFiles(fakeXlsxFile)
  await page.locator('#workflow-upload-section form.upload-form button[type="submit"]').click()

  await expect(page.getByText('请至少上传一份试卷文件（文档或图片）')).toBeVisible()
})

test('exam upload validates missing score file before request', async ({ page }) => {
  await openTeacherApp(page, {
    stateOverrides: {
      teacherWorkbenchTab: 'workflow',
    },
  })

  await page.getByRole('button', { name: '考试', exact: true }).first().click()
  await page.locator('#workflow-upload-section input[type="file"]').nth(0).setInputFiles(fakePdfFile)
  await page.locator('#workflow-upload-section form.upload-form button[type="submit"]').click()

  await expect(page.getByText('请至少上传一份成绩文件（表格文件或文档/图片）')).toBeVisible()
})
