import { access, mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { expect, test } from '@playwright/test'
import { setupBasicTeacherApiMocks, setupTeacherState } from './helpers/teacherHarness'
import { assignmentConfirmButton, workflowStatusChip } from './helpers/workflowLocators'

const parseJson = async (filePath: string) => JSON.parse(await readFile(filePath, 'utf-8'))

const buildAssignmentDraft = (jobId: string, assignmentId: string) => ({
  job_id: jobId,
  assignment_id: assignmentId,
  date: '2026-02-08',
  scope: 'public',
  delivery_mode: 'pdf',
  requirements: {
    subject: '物理',
    topic: '电场综合',
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

test('assignment confirm writes manifest and question artifacts consistently', async ({ page }) => {
  const tmpRoot = await mkdtemp(path.join(os.tmpdir(), 'teacher-e2e-fs-assignment-'))
  const jobId = 'job_fs_assignment_1'
  const assignmentId = 'A-FS-001'

  try {
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
        body: JSON.stringify({ job_id: jobId, status: 'done', progress: 100, assignment_id: assignmentId }),
      })
    })

    await page.route('http://localhost:8000/assignment/upload/draft**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, draft: buildAssignmentDraft(jobId, assignmentId) }),
      })
    })

    await page.route('http://localhost:8000/assignment/upload/draft/save', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
    })

    await page.route('http://localhost:8000/teacher/assignment/progress**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, assignment_id: assignmentId, students: [] }),
      })
    })

    await page.route('http://localhost:8000/assignment/upload/confirm', async (route) => {
      const assignmentDir = path.join(tmpRoot, 'data', 'assignments', assignmentId)
      await mkdir(assignmentDir, { recursive: true })
      await writeFile(
        path.join(assignmentDir, 'manifest.json'),
        JSON.stringify({ assignment_id: assignmentId, question_count: 1, scope: 'public' }, null, 2),
      )
      await writeFile(
        path.join(assignmentDir, 'questions.json'),
        JSON.stringify([{ id: 1, stem: '题干示例' }], null, 2),
      )

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, message: '作业已确认创建。', assignment_id: assignmentId, question_count: 1 }),
      })
    })

    await page.goto('/')
    const confirmBtn = assignmentConfirmButton(page)
    await confirmBtn.click()
    await expect(confirmBtn).toHaveText('已创建')

    const manifestPath = path.join(tmpRoot, 'data', 'assignments', assignmentId, 'manifest.json')
    const questionsPath = path.join(tmpRoot, 'data', 'assignments', assignmentId, 'questions.json')

    const manifest = await parseJson(manifestPath)
    const questions = await parseJson(questionsPath)

    expect(manifest.assignment_id).toBe(assignmentId)
    expect(manifest.question_count).toBe(questions.length)
    expect(Array.isArray(questions)).toBe(true)
  } finally {
    await rm(tmpRoot, { recursive: true, force: true })
  }
})

test('assignment confirm failure does not produce filesystem artifacts', async ({ page }) => {
  const tmpRoot = await mkdtemp(path.join(os.tmpdir(), 'teacher-e2e-fs-assignment-fail-'))
  const jobId = 'job_fs_assignment_fail_1'
  const assignmentId = 'A-FS-FAIL-001'

  try {
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
        body: JSON.stringify({ job_id: jobId, status: 'done', progress: 100, assignment_id: assignmentId }),
      })
    })

    await page.route('http://localhost:8000/assignment/upload/draft**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, draft: buildAssignmentDraft(jobId, assignmentId) }),
      })
    })

    await page.route('http://localhost:8000/assignment/upload/draft/save', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
    })

    await page.route('http://localhost:8000/assignment/upload/confirm', async (route) => {
      await route.fulfill({ status: 500, contentType: 'text/plain', body: 'confirm assignment failed' })
    })

    await page.goto('/')
    await assignmentConfirmButton(page).click()
    await expect(page.locator('#workflow-assignment-draft-section').getByText('confirm assignment failed')).toBeVisible()

    const manifestPath = path.join(tmpRoot, 'data', 'assignments', assignmentId, 'manifest.json')
    await expect(access(manifestPath)).rejects.toThrow()
  } finally {
    await rm(tmpRoot, { recursive: true, force: true })
  }
})

test('assignment confirm remains idempotent in artifact output when clicked repeatedly', async ({ page }) => {
  const tmpRoot = await mkdtemp(path.join(os.tmpdir(), 'teacher-e2e-fs-assignment-idempotent-'))
  const jobId = 'job_fs_assignment_idempotent_1'
  const assignmentId = 'A-FS-IDEMPOTENT-001'
  let confirmCalls = 0

  try {
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
        body: JSON.stringify({ job_id: jobId, status: 'done', progress: 100, assignment_id: assignmentId }),
      })
    })

    await page.route('http://localhost:8000/assignment/upload/draft**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, draft: buildAssignmentDraft(jobId, assignmentId) }),
      })
    })

    await page.route('http://localhost:8000/assignment/upload/draft/save', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
    })

    await page.route('http://localhost:8000/teacher/assignment/progress**', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, students: [] }) })
    })

    await page.route('http://localhost:8000/assignment/upload/confirm', async (route) => {
      confirmCalls += 1
      const assignmentDir = path.join(tmpRoot, 'data', 'assignments', assignmentId)
      await mkdir(assignmentDir, { recursive: true })
      await writeFile(
        path.join(assignmentDir, 'manifest.json'),
        JSON.stringify({ assignment_id: assignmentId, write_seq: confirmCalls }, null, 2),
      )
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, assignment_id: assignmentId, message: '作业已确认创建。' }),
      })
    })

    await page.goto('/')
    const confirmBtn = assignmentConfirmButton(page)
    await confirmBtn.click()
    await confirmBtn.evaluate((node) => (node as HTMLButtonElement).click())

    await expect.poll(() => confirmCalls).toBe(1)
    await expect(confirmBtn).toHaveText('已创建')

    const manifestPath = path.join(tmpRoot, 'data', 'assignments', assignmentId, 'manifest.json')
    await expect.poll(async () => {
      try {
        await access(manifestPath)
        return true
      } catch {
        return false
      }
    }).toBe(true)

    const manifest = await parseJson(manifestPath)
    expect(manifest.write_seq).toBe(1)
  } finally {
    await rm(tmpRoot, { recursive: true, force: true })
  }
})



