import { expect, test } from '@playwright/test'
import { openTeacherApp } from './helpers/teacherHarness'
import {
  assignmentConfirmButton,
  workflowKindOption,
  workflowKindSourcePicker,
  workflowSourceOption,
  workflowUploadSection,
  workflowUploadSubmitButton,
} from './helpers/workflowLocators'

const ASSIGNMENT_ID = 'HW-SCENARIO-E2E'
const JOB_ID = 'job_scenario_kind_1'

const fakePdfFile = {
  name: 'scenario-brief.pdf',
  mimeType: 'application/pdf',
  buffer: Buffer.from('%PDF-1.4 scenario-brief'),
}

const scenarioDraft = {
  job_id: JOB_ID,
  assignment_id: ASSIGNMENT_ID,
  date: '2026-10-12',
  scope: 'public',
  delivery_mode: 'pdf',
  assignment_kind: 'scenario',
  content_source: 'upload',
  question_count: 0,
  requirements: {
    subject: '物理',
    topic: '测量误差',
    grade_level: '高二',
    brief: '围绕老师材料讨论测量约束，不要另编情节。',
    discussion_goals: ['指出情景约束'],
    extra_constraints: '',
    rubric: '',
  },
  requirements_missing: [],
  questions: [],
  draft_saved: true,
}

test('scenario picker uses non-8-point upload copy then publishes draft via testid', async ({ page }) => {
  let startBody = ''
  let confirmCalls = 0
  const saveBodies: Array<Record<string, unknown>> = []

  await openTeacherApp(page, {
    stateOverrides: {
      teacherWorkbenchTab: 'workflow',
    },
  })

  await page.route('http://localhost:8000/assignment/upload/start', async (route) => {
    if (route.request().method().toUpperCase() !== 'POST') {
      await route.fallback()
      return
    }
    startBody = route.request().postData() || ''
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
        assignment_kind: 'scenario',
        question_count: 0,
        requirements_missing: [],
      }),
    })
  })

  await page.route('http://localhost:8000/assignment/upload/draft**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, draft: scenarioDraft }),
    })
  })

  await page.route('http://localhost:8000/assignment/upload/draft/save', async (route) => {
    saveBodies.push(JSON.parse(route.request().postData() || '{}') as Record<string, unknown>)
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
        message: '作业已发布草稿。',
        assignment_id: ASSIGNMENT_ID,
        question_count: 0,
      }),
    })
  })

  await expect(workflowKindSourcePicker(page)).toBeVisible()
  await expect(workflowUploadSection(page)).toContainText('生成 8 点描述')

  await workflowKindOption(page, 'scenario').check()
  await expect(workflowKindOption(page, 'scenario')).toBeChecked()
  await expect(workflowSourceOption(page, 'upload')).toBeChecked()
  await expect(workflowSourceOption(page, 'bank')).toBeDisabled()

  const uploadSection = workflowUploadSection(page)
  await expect(uploadSection).toContainText('从材料提取作业说明（brief）')
  await expect(uploadSection).toContainText('非做题允许 0 题')
  await expect(uploadSection).toContainText('解析完成后请发布草稿')
  await expect(uploadSection).not.toContainText('生成 8 点描述')

  await page.getByTestId('workflow-upload-assignment-id').fill(ASSIGNMENT_ID)
  await page.getByTestId('workflow-upload-file').setInputFiles(fakePdfFile)
  await workflowUploadSubmitButton(page).click()

  await expect.poll(() => startBody.length).toBeGreaterThan(0)
  expect(startBody).toContain('name="assignment_kind"')
  expect(startBody).toContain('scenario')
  expect(startBody).not.toContain('question_bank')

  const confirmBtn = assignmentConfirmButton(page)
  await expect(confirmBtn).toBeVisible()
  await expect(confirmBtn).toBeEnabled()
  await expect(confirmBtn).toHaveText('发布草稿')
  await expect(page.getByTestId('assignment-confirm-button')).toBeVisible()

  await expect(page.getByText('作业说明（可编辑）')).toBeVisible()
  await expect(page.getByText('作业 8 点要求（可编辑）')).toHaveCount(0)
  await expect(page.getByTestId('draft-brief')).toBeVisible()
  await expect(page.getByTestId('draft-brief')).toHaveValue(/围绕老师材料讨论测量约束/)
  await expect(page.getByTestId('draft-rubric')).toBeVisible()
  await expect(page.getByTestId('draft-allow-practice')).toHaveCount(0)

  await page.getByTestId('draft-rubric').fill('- 能指出情景约束\n- 不另编情节')
  await confirmBtn.click()

  await expect.poll(() => confirmCalls).toBe(1)
  await expect.poll(() => saveBodies.length).toBeGreaterThan(0)
  const savedRequirements = saveBodies[0]?.requirements as Record<string, unknown>
  expect(savedRequirements?.brief).toContain('围绕老师材料讨论测量约束')
  expect(savedRequirements?.rubric).toContain('能指出情景约束')
  expect(saveBodies[0]?.questions).toEqual([])
  await expect(page.getByTestId('assignment-confirm-button')).toHaveText('已发布')
})
