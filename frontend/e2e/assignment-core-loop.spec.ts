import { expect, test, type Page } from '@playwright/test'
import { openStudentApp } from './helpers/studentHarness'
import { openTeacherApp } from './helpers/teacherHarness'
import { assignmentConfirmButton, workflowUploadSubmitButton } from './helpers/workflowLocators'

const ASSIGNMENT_ID = 'HW-LOOP-001'
const JOB_ID = 'job_loop_1'
const STUDENT_BASE_URL = 'http://127.0.0.1:4275'

const fakePdfFile = {
  name: 'assignment-loop.pdf',
  mimeType: 'application/pdf',
  buffer: Buffer.from('%PDF-1.4 assignment-loop'),
}

const buildAssignmentDraft = (jobId: string, assignmentId: string) => ({
  job_id: jobId,
  assignment_id: assignmentId,
  date: '2026-09-05',
  scope: 'public',
  delivery_mode: 'pdf',
  requirements: {
    subject: '物理',
    topic: '电场强度',
    grade_level: '高二',
    class_level: '中等',
    core_concepts: ['电场', '电势', '电场线'],
    typical_problem: '受力分析',
    misconceptions: ['方向错误', '单位混乱', '漏条件', '乱代数'],
    duration_minutes: 40,
    preferences: ['分层训练'],
    extra_constraints: '',
  },
  requirements_missing: [],
  questions: [{ id: 1, stem: '题干示例' }],
  draft_saved: true,
})

const progressPayload = (submitted: number) => ({
  ok: true,
  assignment_id: ASSIGNMENT_ID,
  date: '2026-09-05',
  counts: {
    expected: 1,
    discussion_pass: 0,
    submitted,
    completed: submitted,
    overdue: 0,
  },
  students: [
    {
      student_id: 'S001',
      student_name: '测试学生',
      complete: submitted > 0,
      discussion: { pass: false },
      submission: { attempts: submitted },
    },
  ],
})

const mockTeacherAssignmentApis = async (page: Page, submittedCount: { value: number }) => {
  let confirmCalls = 0

  await page.route('http://localhost:8000/assignment/upload/start', async (route) => {
    if (route.request().method().toUpperCase() !== 'POST') {
      await route.fallback()
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        job_id: JOB_ID,
        message: '解析任务已创建。',
      }),
    })
  })

  await page.route('http://localhost:8000/assignment/upload/status**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        job_id: JOB_ID,
        status: 'done',
        progress: 100,
        assignment_id: ASSIGNMENT_ID,
        requirements_missing: [],
      }),
    })
  })

  await page.route('http://localhost:8000/assignment/upload/draft**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, draft: buildAssignmentDraft(JOB_ID, ASSIGNMENT_ID) }),
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
    confirmCalls += 1
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        message: '作业已确认创建。',
        assignment_id: ASSIGNMENT_ID,
        question_count: 1,
      }),
    })
  })

  await page.route('http://localhost:8000/teacher/assignment/progress**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(progressPayload(submittedCount.value)),
    })
  })

  return {
    getConfirmCalls: () => confirmCalls,
  }
}

test('mocked assignment how-to loop covers upload confirm today submit and progress', async ({ page, browser }) => {
  const submittedCount = { value: 0 }
  const teacherPage = page
  const studentContext = await browser.newContext({
    baseURL: STUDENT_BASE_URL,
    viewport: { width: 1280, height: 800 },
  })
  const studentPage = await studentContext.newPage()

  try {
    await openTeacherApp(teacherPage, {
      stateOverrides: {
        teacherWorkbenchTab: 'workflow',
      },
    })
    const teacherMocks = await mockTeacherAssignmentApis(teacherPage, submittedCount)

    await teacherPage.getByTestId('workflow-upload-assignment-id').fill(ASSIGNMENT_ID)
    await teacherPage.getByTestId('workflow-upload-file').setInputFiles(fakePdfFile)
    await workflowUploadSubmitButton(teacherPage).click()

    await expect
      .poll(async () =>
        teacherPage.evaluate(() => {
          const raw = localStorage.getItem('teacherActiveUpload')
          return raw ? JSON.parse(raw) : null
        }),
      )
      .toEqual({ type: 'assignment', job_id: JOB_ID })

    const confirmBtn = assignmentConfirmButton(teacherPage)
    await expect(confirmBtn).toBeVisible()
    await expect(confirmBtn).toBeEnabled()
    await expect(confirmBtn).toHaveText('创建作业')
    await expect(teacherPage.getByTestId('workflow-summary-status-chip').first()).toContainText('待审核')

    await confirmBtn.click()
    await expect.poll(() => teacherMocks.getConfirmCalls()).toBe(1)

    const progressSection = teacherPage.getByTestId('workflow-progress-section')
    await expect(progressSection).toContainText('已提交：0')
    await expect(progressSection.getByTestId('progress-row-S001')).toBeVisible()

    await openStudentApp(studentPage, {
      apiMocks: {
        todayAssignment: {
          assignment_id: ASSIGNMENT_ID,
          date: '2026-09-05',
        },
      },
    })
    await studentPage.route('http://localhost:8000/student/submit', async (route) => {
      submittedCount.value = 1
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          submitted: true,
          assignment_id: ASSIGNMENT_ID,
          attempt_id: 'attempt_loop_1',
          official_score: 8,
        }),
      })
    })

    await expect(studentPage.getByTestId('student-today-home')).toBeVisible()
    await expect(studentPage.getByTestId('student-today-assignment-list')).toBeVisible()
    await expect(studentPage.getByTestId('student-today-assignment-list')).toContainText(ASSIGNMENT_ID)
    await expect(studentPage.getByText('老师尚未布置')).toHaveCount(0)

    await studentPage.getByTestId('student-today-assignment-list').getByRole('button', { name: '提交作业' }).click()
    await expect(studentPage.getByTestId('student-submit-panel')).toBeVisible()
    await studentPage.getByTestId('student-submit-file').setInputFiles(fakePdfFile)
    await studentPage.getByRole('button', { name: '提交作业' }).click()
    await expect(studentPage.getByTestId('student-submit-success')).toBeVisible()
    await expect(studentPage.getByTestId('student-submit-result')).toContainText('已提交')

    await teacherPage.getByTestId('progress-refresh').click()
    await expect(progressSection).toContainText('已提交：1')
  } finally {
    await studentContext.close()
  }
})
