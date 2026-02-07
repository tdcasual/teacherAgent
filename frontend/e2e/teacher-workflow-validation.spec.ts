import { expect, test } from '@playwright/test'
import { openTeacherApp, setupBasicTeacherApiMocks, setupTeacherState } from './helpers/teacherHarness'

const fakePdfFile = {
  name: 'sample.pdf',
  mimeType: 'application/pdf',
  buffer: Buffer.from('%PDF-1.4 sample'),
}

test('assignment upload validation requires assignment id before request', async ({ page }) => {
  let uploadCalls = 0
  const { chatStartCalls } = await openTeacherApp(page, {
    stateOverrides: {
      teacherWorkbenchTab: 'workflow',
    },
  })

  await page.route('http://localhost:8000/assignment/upload/start', async (route) => {
    uploadCalls += 1
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, job_id: 'x' }) })
  })

  await page.locator('#workflow-upload-section form.upload-form button[type="submit"]').click()

  await expect(page.getByText('请填写作业编号')).toBeVisible()
  expect(uploadCalls).toBe(0)
  expect(chatStartCalls.length).toBe(0)
})

test('assignment upload validation requires files after assignment id', async ({ page }) => {
  let uploadCalls = 0
  await openTeacherApp(page, {
    stateOverrides: {
      teacherWorkbenchTab: 'workflow',
    },
  })

  await page.route('http://localhost:8000/assignment/upload/start', async (route) => {
    uploadCalls += 1
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, job_id: 'x' }) })
  })

  await page.getByPlaceholder('例如：HW-2026-02-05').fill('HW-VAL-001')
  await page.locator('#workflow-upload-section form.upload-form button[type="submit"]').click()

  await expect(page.getByText('请至少上传一份作业文件（文档或图片）')).toBeVisible()
  expect(uploadCalls).toBe(0)
})

test('assignment class scope requires class name when file is provided', async ({ page }) => {
  let uploadCalls = 0
  await openTeacherApp(page, {
    stateOverrides: {
      teacherWorkbenchTab: 'workflow',
    },
  })

  await page.route('http://localhost:8000/assignment/upload/start', async (route) => {
    uploadCalls += 1
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, job_id: 'x' }) })
  })

  await page.getByPlaceholder('例如：HW-2026-02-05').fill('HW-VAL-002')
  await page.locator('#workflow-upload-section form.upload-form select').first().selectOption('class')
  await page.locator('#workflow-upload-section input[type="file"]').first().setInputFiles(fakePdfFile)
  await page.locator('#workflow-upload-section form.upload-form button[type="submit"]').click()

  await expect(page.getByText('班级作业请填写班级')).toBeVisible()
  expect(uploadCalls).toBe(0)
})

test('assignment student scope requires student ids when file is provided', async ({ page }) => {
  let uploadCalls = 0
  await openTeacherApp(page, {
    stateOverrides: {
      teacherWorkbenchTab: 'workflow',
    },
  })

  await page.route('http://localhost:8000/assignment/upload/start', async (route) => {
    uploadCalls += 1
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, job_id: 'x' }) })
  })

  await page.getByPlaceholder('例如：HW-2026-02-05').fill('HW-VAL-003')
  await page.locator('#workflow-upload-section form.upload-form select').first().selectOption('student')
  await page.locator('#workflow-upload-section input[type="file"]').first().setInputFiles(fakePdfFile)
  await page.locator('#workflow-upload-section form.upload-form button[type="submit"]').click()

  await expect(page.getByText('私人作业请填写学生编号')).toBeVisible()
  expect(uploadCalls).toBe(0)
})

test('exam upload validation requires score file after paper file exists', async ({ page }) => {
  let examUploadCalls = 0
  await openTeacherApp(page, {
    stateOverrides: {
      teacherWorkbenchTab: 'workflow',
    },
  })

  await page.route('http://localhost:8000/exam/upload/start', async (route) => {
    examUploadCalls += 1
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, job_id: 'x' }) })
  })

  await page.getByRole('button', { name: '考试', exact: true }).first().click()
  await page.locator('#workflow-upload-section input[type="file"]').first().setInputFiles(fakePdfFile)
  await page.locator('#workflow-upload-section form.upload-form button[type="submit"]').click()

  await expect(page.getByText('请至少上传一份成绩文件（表格文件或文档/图片）')).toBeVisible()
  expect(examUploadCalls).toBe(0)
})

test('assignment confirm stays disabled when requirements are missing', async ({ page }) => {
  const jobId = 'job_assignment_missing_requirements'
  let confirmCalls = 0

  await setupTeacherState(page, {
    stateOverrides: {
      teacherWorkbenchTab: 'workflow',
      teacherActiveUpload: JSON.stringify({ type: 'assignment', job_id: jobId }),
    },
  })
  await setupBasicTeacherApiMocks(page)

  await page.route('http://localhost:8000/assignment/upload/status**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        job_id: jobId,
        status: 'done',
        progress: 100,
        assignment_id: 'HW-MISSING-001',
        requirements_missing: ['topic', 'misconceptions'],
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
          job_id: jobId,
          assignment_id: 'HW-MISSING-001',
          date: '2026-02-07',
          scope: 'public',
          delivery_mode: 'pdf',
          requirements: {
            subject: '物理',
            topic: '',
            grade_level: '高二',
            class_level: '中等',
            core_concepts: [],
            typical_problem: '',
            misconceptions: [],
            duration_minutes: 40,
            preferences: [],
            extra_constraints: '',
          },
          requirements_missing: ['topic', 'misconceptions'],
          questions: [{ id: 1, stem: '题干' }],
        },
      }),
    })
  })

  await page.route('http://localhost:8000/assignment/upload/confirm', async (route) => {
    confirmCalls += 1
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true }),
    })
  })

  await page.goto('/')

  const confirmBtn = page.locator('.confirm-btn')
  await expect(confirmBtn).toBeVisible()
  await expect(confirmBtn).toBeDisabled()
  await expect(confirmBtn).toHaveAttribute('title', /请先补全/) 

  await confirmBtn.evaluate((node) => {
    ;(node as HTMLButtonElement).click()
  })
  expect(confirmCalls).toBe(0)
})

test('recovers exam workflow mode from teacherActiveUpload local state', async ({ page }) => {
  const examJobId = 'exam_job_recover_1'

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
        status: 'processing',
        progress: 52,
      }),
    })
  })

  await page.goto('/')
  await expect(page.getByRole('button', { name: '考试', exact: true }).first()).toHaveClass(/active/)
  await expect(page.getByText('上传考试文件（试卷 + 成绩表）')).toBeVisible()
})
