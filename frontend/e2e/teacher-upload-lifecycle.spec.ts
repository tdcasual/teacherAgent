import { expect, test } from '@playwright/test'
import { openTeacherApp, setupBasicTeacherApiMocks, setupTeacherState } from './helpers/teacherHarness'

const fakePdfFile = {
  name: 'sample.pdf',
  mimeType: 'application/pdf',
  buffer: Buffer.from('%PDF-1.4 sample'),
}

const fakeXlsxFile = {
  name: 'scores.xlsx',
  mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  buffer: Buffer.from('xlsx-sample'),
}

test('assignment upload success writes teacherActiveUpload and displays status message', async ({ page }) => {
  let uploadCalls = 0

  await openTeacherApp(page, {
    stateOverrides: {
      teacherWorkbenchTab: 'workflow',
    },
  })

  await page.route('http://localhost:8000/assignment/upload/start', async (route) => {
    uploadCalls += 1
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        job_id: 'job_upload_assignment_1',
        message: '解析任务已创建。',
      }),
    })
  })

  await page.getByPlaceholder('例如：HW-2026-02-05').fill('HW-UP-001')
  await page.locator('#workflow-upload-section input[type="file"]').first().setInputFiles(fakePdfFile)
  await page.locator('#workflow-upload-section form.upload-form button[type="submit"]').click()

  await expect.poll(async () =>
    page.evaluate(() => {
      const raw = localStorage.getItem('teacherActiveUpload')
      if (!raw) return null
      return JSON.parse(raw)
    }),
  ).toEqual({ type: 'assignment', job_id: 'job_upload_assignment_1' })
  expect(uploadCalls).toBe(1)
})

test('exam upload success writes teacherActiveUpload and displays status message', async ({ page }) => {
  let examUploadCalls = 0

  await openTeacherApp(page, {
    stateOverrides: {
      teacherWorkbenchTab: 'workflow',
    },
  })

  await page.route('http://localhost:8000/exam/upload/start', async (route) => {
    examUploadCalls += 1
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        job_id: 'job_upload_exam_1',
        message: '考试解析任务已创建。',
      }),
    })
  })

  await page.getByRole('button', { name: '考试', exact: true }).first().click()
  await page.locator('#workflow-upload-section input[type="file"]').nth(0).setInputFiles(fakePdfFile)
  await page.locator('#workflow-upload-section input[type="file"]').nth(2).setInputFiles(fakeXlsxFile)
  await page.locator('#workflow-upload-section form.upload-form button[type="submit"]').click()

  await expect.poll(async () =>
    page.evaluate(() => {
      const raw = localStorage.getItem('teacherActiveUpload')
      if (!raw) return null
      return JSON.parse(raw)
    }),
  ).toEqual({ type: 'exam', job_id: 'job_upload_exam_1' })
  expect(examUploadCalls).toBe(1)
})

test('assignment active upload marker is cleared when status becomes confirmed', async ({ page }) => {
  const assignmentJobId = 'job_assignment_confirmed_1'

  await setupTeacherState(page, {
    stateOverrides: {
      teacherWorkbenchTab: 'workflow',
      teacherActiveUpload: JSON.stringify({ type: 'assignment', job_id: assignmentJobId }),
    },
  })
  await setupBasicTeacherApiMocks(page)

  await page.route('http://localhost:8000/assignment/upload/status**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        job_id: assignmentJobId,
        status: 'confirmed',
        progress: 100,
        assignment_id: 'HW-OK-001',
      }),
    })
  })

  await page.route('http://localhost:8000/assignment/upload/draft**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        draft: {
          job_id: assignmentJobId,
          assignment_id: 'HW-OK-001',
          date: '2026-02-07',
          scope: 'public',
          delivery_mode: 'pdf',
          requirements: {
            subject: '物理',
            topic: '电场',
            grade_level: '高二',
            class_level: '中等',
            core_concepts: ['电场'],
            typical_problem: '受力分析',
            misconceptions: ['单位混淆', '方向错误', '漏条件', '乱代数'],
            duration_minutes: 40,
            preferences: ['分层'],
            extra_constraints: '无',
          },
          requirements_missing: [],
          questions: [{ id: 1, stem: '题干' }],
        },
      }),
    })
  })

  await page.goto('/')

  await expect.poll(async () => page.evaluate(() => localStorage.getItem('teacherActiveUpload'))).toBeNull()
})

test('exam active upload marker is cleared when status becomes failed', async ({ page }) => {
  const examJobId = 'job_exam_failed_1'

  await setupTeacherState(page, {
    stateOverrides: {
      teacherWorkbenchTab: 'workflow',
      teacherActiveUpload: JSON.stringify({ type: 'exam', job_id: examJobId }),
    },
  })
  await setupBasicTeacherApiMocks(page)

  await page.route('http://localhost:8000/exam/upload/status**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        job_id: examJobId,
        status: 'failed',
        error: '解析失败',
      }),
    })
  })

  await page.goto('/')

  await expect(page.locator('.workflow-chip.error')).toHaveText('解析失败')
  await expect.poll(async () => page.evaluate(() => localStorage.getItem('teacherActiveUpload'))).toBeNull()
})

test('exam upload validation requires paper file before start request', async ({ page }) => {
  let examUploadCalls = 0

  await openTeacherApp(page, {
    stateOverrides: {
      teacherWorkbenchTab: 'workflow',
    },
  })

  await page.route('http://localhost:8000/exam/upload/start', async (route) => {
    examUploadCalls += 1
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, job_id: 'unused' }),
    })
  })

  await page.getByRole('button', { name: '考试', exact: true }).first().click()
  await page.locator('#workflow-upload-section form.upload-form button[type="submit"]').click()

  await expect(page.getByText('请至少上传一份试卷文件（文档或图片）')).toBeVisible()
  expect(examUploadCalls).toBe(0)
})

test('assignment class scope with complete fields sends exactly one upload request', async ({ page }) => {
  let uploadCalls = 0

  await openTeacherApp(page, {
    stateOverrides: {
      teacherWorkbenchTab: 'workflow',
    },
  })

  await page.route('http://localhost:8000/assignment/upload/start', async (route) => {
    uploadCalls += 1
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        job_id: 'job_upload_assignment_2',
      }),
    })
  })

  await page.getByPlaceholder('例如：HW-2026-02-05').fill('HW-UP-CLASS-1')
  await page.locator('#workflow-upload-section form.upload-form select').first().selectOption('class')
  await page.locator("#workflow-upload-section input[placeholder='例如：高二2403班']").fill('高二2403班')
  await page.locator('#workflow-upload-section input[type="file"]').first().setInputFiles(fakePdfFile)

  await page.locator('#workflow-upload-section form.upload-form button[type="submit"]').click()

  await expect.poll(() => uploadCalls).toBe(1)
})
