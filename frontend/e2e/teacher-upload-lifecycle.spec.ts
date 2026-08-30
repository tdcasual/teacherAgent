import { expect, test } from '@playwright/test'
import { openTeacherApp, setupBasicTeacherApiMocks, setupTeacherState } from './helpers/teacherHarness'
import {
  workflowAssignmentScopeSelect,
  workflowUploadSubmitButton,
} from './helpers/workflowLocators'

const fakePdfFile = {
  name: 'sample.pdf',
  mimeType: 'application/pdf',
  buffer: Buffer.from('%PDF-1.4 sample'),
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
  await workflowUploadSubmitButton(page).click()

  await expect.poll(async () =>
    page.evaluate(() => {
      const raw = localStorage.getItem('teacherActiveUpload')
      if (!raw) return null
      return JSON.parse(raw)
    }),
  ).toEqual({ type: 'assignment', job_id: 'job_upload_assignment_1' })
  expect(uploadCalls).toBe(1)
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
  await workflowAssignmentScopeSelect(page).selectOption('class')
  await page.locator("#workflow-upload-section input[placeholder='例如：高二2403班']").fill('高二2403班')
  await page.locator('#workflow-upload-section input[type="file"]').first().setInputFiles(fakePdfFile)

  await workflowUploadSubmitButton(page).click()

  await expect.poll(() => uploadCalls).toBe(1)
})
