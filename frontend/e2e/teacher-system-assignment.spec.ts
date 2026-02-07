import { expect, test } from '@playwright/test'
import { openTeacherApp, setupBasicTeacherApiMocks, setupTeacherState } from './helpers/teacherHarness'

const fakePdfFile = {
  name: 'assignment.pdf',
  mimeType: 'application/pdf',
  buffer: Buffer.from('%PDF-1.4 assignment'),
}

const buildAssignmentDraft = (jobId: string, assignmentId: string) => ({
  job_id: jobId,
  assignment_id: assignmentId,
  date: '2026-02-08',
  scope: 'public',
  delivery_mode: 'pdf',
  requirements: {
    subject: '物理',
    topic: '电学复习',
    grade_level: '高二',
    class_level: '中等',
    core_concepts: ['电场', '电势'],
    typical_problem: '综合应用',
    misconceptions: ['方向错误', '单位混乱', '边界遗漏', '公式误用'],
    duration_minutes: 40,
    preferences: ['分层训练'],
    extra_constraints: '无',
  },
  requirements_missing: [],
  questions: [{ id: 1, stem: '题干示例' }],
})

test('progress refresh loads students and incomplete toggle filters rows', async ({ page }) => {
  let progressCalls = 0
  let lastProgressUrl = ''

  await openTeacherApp(page, {
    stateOverrides: {
      teacherWorkbenchTab: 'workflow',
    },
  })

  await page.route('http://localhost:8000/teacher/assignment/progress**', async (route) => {
    progressCalls += 1
    lastProgressUrl = route.request().url()
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        assignment_id: 'A-SYS-001',
        date: '2026-02-08',
        counts: {
          expected: 2,
          discussion_pass: 1,
          submitted: 1,
          completed: 1,
          overdue: 0,
        },
        students: [
          {
            student_id: 'S-INCOMPLETE',
            student_name: '未完成同学',
            complete: false,
            discussion: { pass: false },
            submission: { attempts: 0 },
          },
          {
            student_id: 'S-COMPLETE',
            student_name: '已完成同学',
            complete: true,
            discussion: { pass: true },
            submission: { attempts: 1, best: { score_earned: 85 } },
          },
        ],
      }),
    })
  })

  const progressSection = page.locator('#workflow-progress-section')
  await progressSection.getByRole('button', { name: '展开' }).click()
  await progressSection.getByPlaceholder('例如：A2403_2026-02-04').fill('A-SYS-001')
  await progressSection.getByRole('button', { name: '刷新' }).click()

  await expect.poll(() => progressCalls).toBe(1)
  expect(lastProgressUrl).toContain('assignment_id=A-SYS-001')
  expect(lastProgressUrl).toContain('include_students=true')

  await expect(progressSection.getByText('S-INCOMPLETE')).toBeVisible()
  await expect(progressSection.getByText('S-COMPLETE')).toHaveCount(0)

  await progressSection.getByLabel('只看未完成').uncheck()
  await expect(progressSection.getByText('S-COMPLETE')).toBeVisible()
})

test('progress refresh button enters loading state while request is pending', async ({ page }) => {
  await openTeacherApp(page, {
    stateOverrides: {
      teacherWorkbenchTab: 'workflow',
    },
  })

  await page.route('http://localhost:8000/teacher/assignment/progress**', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 260))
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, assignment_id: 'A-SYS-002', students: [] }),
    })
  })

  const progressSection = page.locator('#workflow-progress-section')
  await progressSection.getByRole('button', { name: '展开' }).click()
  await progressSection.getByPlaceholder('例如：A2403_2026-02-04').fill('A-SYS-002')
  await progressSection.getByRole('button', { name: '刷新' }).click()

  await expect(progressSection.getByRole('button', { name: '加载中…' })).toBeVisible()
  await expect(progressSection.getByRole('button', { name: '刷新' })).toBeVisible()
})

test('progress request error is surfaced in workflow panel', async ({ page }) => {
  await openTeacherApp(page, {
    stateOverrides: {
      teacherWorkbenchTab: 'workflow',
    },
  })

  await page.route('http://localhost:8000/teacher/assignment/progress**', async (route) => {
    await route.fulfill({
      status: 500,
      contentType: 'text/plain',
      body: 'progress backend unavailable',
    })
  })

  const progressSection = page.locator('#workflow-progress-section')
  await progressSection.getByRole('button', { name: '展开' }).click()
  await progressSection.getByPlaceholder('例如：A2403_2026-02-04').fill('A-SYS-003')
  await progressSection.getByRole('button', { name: '刷新' }).click()

  await expect(progressSection.getByText('progress backend unavailable')).toBeVisible()
})

test('assignment upload request uses updated API base from settings', async ({ page }) => {
  let customBaseUploadCalls = 0

  await openTeacherApp(page, {
    stateOverrides: {
      teacherWorkbenchTab: 'workflow',
    },
  })

  await page.route('http://127.0.0.1:9100/**', async (route) => {
    const { pathname } = new URL(route.request().url())
    if (pathname === '/assignment/upload/start') {
      customBaseUploadCalls += 1
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, job_id: 'job_custom_base_assignment' }),
      })
      return
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
  })

  await page.getByRole('button', { name: '设置' }).click()
  await page.getByPlaceholder('http://localhost:8000').fill('http://127.0.0.1:9100')

  await page.getByPlaceholder('例如：HW-2026-02-05').fill('HW-SYS-BASE-001')
  await page.locator('#workflow-upload-section input[type="file"]').first().setInputFiles(fakePdfFile)
  await page.locator('#workflow-upload-section form.upload-form button[type="submit"]').click()

  await expect.poll(() => customBaseUploadCalls).toBe(1)
})

test('assignment confirm success triggers progress fetch with returned assignment id', async ({ page }) => {
  const jobId = 'job_assignment_system_confirm_1'
  let progressCalls = 0
  let lastProgressUrl = ''

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
        assignment_id: 'A-SYS-CONFIRM-001',
      }),
    })
  })

  await page.route('http://localhost:8000/assignment/upload/draft**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, draft: buildAssignmentDraft(jobId, 'A-SYS-CONFIRM-001') }),
    })
  })

  await page.route('http://localhost:8000/assignment/upload/draft/save', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, message: '草稿已保存。' }),
    })
  })

  await page.route('http://localhost:8000/assignment/upload/confirm', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        message: '作业已确认创建。',
        assignment_id: 'A-SYS-CONFIRM-001',
        question_count: 1,
      }),
    })
  })

  await page.route('http://localhost:8000/teacher/assignment/progress**', async (route) => {
    progressCalls += 1
    lastProgressUrl = route.request().url()
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        assignment_id: 'A-SYS-CONFIRM-001',
        counts: { expected: 1, completed: 0, submitted: 0, discussion_pass: 0, overdue: 0 },
        students: [
          {
            student_id: 'S001',
            student_name: '学生1',
            complete: false,
            discussion: { pass: false },
            submission: { attempts: 0 },
          },
        ],
      }),
    })
  })

  await page.goto('/')

  const confirmBtn = page.locator('.confirm-btn')
  await expect(confirmBtn).toBeVisible()
  await expect(confirmBtn).toBeEnabled()
  await confirmBtn.click()

  await expect.poll(() => progressCalls).toBeGreaterThan(0)
  expect(lastProgressUrl).toContain('assignment_id=A-SYS-CONFIRM-001')
  await expect(page.locator('#workflow-progress-section')).toContainText('S001')
})
