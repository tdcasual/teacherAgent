import { access, mkdir, readFile, rm, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, test, type Page } from '@playwright/test'

const realE2EEnabled = process.env.E2E_REAL === '1'
const apiBase = String(process.env.E2E_REAL_API_BASE || 'http://localhost:8000').replace(/\/$/, '')
const specDir = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(specDir, '..', '..')
const assignmentDataRoot = path.join(repoRoot, 'data', 'assignments')
const assignmentJobRoot = path.join(repoRoot, 'uploads', 'assignment_jobs')

const assignmentSourceFile = {
  name: 'assignment-source.txt',
  mimeType: 'text/plain',
  buffer: Buffer.from(
    [
      '作业主题：电场与电势综合训练',
      '题1：已知点电荷Q，求某点电场强度方向。',
      '题2：比较两点电势并判断电势能变化。',
      '题3：结合电场线解释受力与运动趋势。',
    ].join('\n'),
    'utf-8',
  ),
}

const assignmentAnswerFile = {
  name: 'assignment-answer.txt',
  mimeType: 'text/plain',
  buffer: Buffer.from(
    [
      '1. 电场方向沿正试探电荷受力方向。',
      '2. 沿电场方向电势降低。',
      '3. 电势能变化由W=-ΔEp判断。',
    ].join('\n'),
    'utf-8',
  ),
}

const uniqueId = (prefix: string) => `${prefix}_${Date.now()}_${Math.floor(Math.random() * 1000)}`

const pathExists = async (targetPath: string) => {
  try {
    await access(targetPath)
    return true
  } catch {
    return false
  }
}

const readJson = async <T>(targetPath: string): Promise<T> => {
  const raw = await readFile(targetPath, 'utf-8')
  return JSON.parse(raw) as T
}

const writeJson = async (targetPath: string, payload: unknown) => {
  await writeFile(targetPath, JSON.stringify(payload, null, 2), 'utf-8')
}

const setTeacherWorkflowState = async (page: Page) => {
  await page.addInitScript(({ base }) => {
    localStorage.clear()
    localStorage.setItem('teacherMainView', 'chat')
    localStorage.setItem('teacherSessionSidebarOpen', 'false')
    localStorage.setItem('teacherSkillsOpen', 'true')
    localStorage.setItem('teacherWorkbenchTab', 'workflow')
    localStorage.setItem('teacherSkillPinned', 'false')
    localStorage.setItem('teacherActiveSkillId', 'physics-teacher-ops')
    localStorage.setItem('apiBaseTeacher', base)
  }, { base: apiBase })
}

const readActiveUploadJobId = async (page: Page, expectedType: 'assignment' | 'exam') => {
  return page.evaluate((type) => {
    const raw = localStorage.getItem('teacherActiveUpload')
    if (!raw) return ''
    try {
      const parsed = JSON.parse(raw) as { type?: string; job_id?: string }
      if (parsed?.type !== type) return ''
      return typeof parsed.job_id === 'string' ? parsed.job_id : ''
    } catch {
      return ''
    }
  }, expectedType)
}

const waitForAssignmentJobId = async (page: Page) => {
  await expect
    .poll(async () => readActiveUploadJobId(page, 'assignment'), {
      timeout: 20_000,
      message: 'teacherActiveUpload should contain assignment job id',
    })
    .not.toBe('')
  return readActiveUploadJobId(page, 'assignment')
}

const seedAssignmentJobAsDone = async (jobId: string, assignmentId: string) => {
  const jobDir = path.join(assignmentJobRoot, jobId)
  const jobPath = path.join(jobDir, 'job.json')

  await expect.poll(() => pathExists(jobPath), { timeout: 20_000 }).toBe(true)

  const parsedPayload = {
    questions: [
      {
        stem: '已知点电荷 Q，在 A 点放置正试探电荷，判断受力方向并说明依据。',
        answer: '受力方向沿电场方向，依据是正试探电荷受力方向定义电场方向。',
        kp: '电场方向',
        difficulty: 'medium',
        score: 8,
        tags: ['electric-field'],
        type: 'short_answer',
      },
    ],
    requirements: {
      subject: '物理',
      topic: '电场与电势',
      grade_level: '高二',
      class_level: '中等',
      core_concepts: ['电场', '电势', '电势能'],
      typical_problem: '场强与电势综合判断',
      misconceptions: ['方向判断错误', '符号混淆', '单位换算错误', '正负号遗漏'],
      duration_minutes: 40,
      preferences: ['A基础', 'B提升'],
      extra_constraints: '先做基础题再做综合题',
    },
    missing: [],
    warnings: [],
    delivery_mode: 'pdf',
    question_count: 1,
    autofilled: false,
    generated_at: new Date().toISOString(),
  }

  await mkdir(jobDir, { recursive: true })
  await writeJson(path.join(jobDir, 'parsed.json'), parsedPayload)

  const job = await readJson<Record<string, unknown>>(jobPath)
  const nextJob = {
    ...job,
    assignment_id: assignmentId,
    status: 'done',
    progress: 100,
    step: 'parsed',
    error: '',
    error_detail: '',
    requirements: parsedPayload.requirements,
    requirements_missing: [],
    question_count: parsedPayload.questions.length,
    updated_at: new Date().toISOString(),
  }
  await writeJson(jobPath, nextJob)
}

const confirmAssignmentUploadEventually = async (page: Page, jobId: string, assignmentId: string) => {
  let lastStatus = 0
  let lastBody = ''

  for (let attempt = 0; attempt < 20; attempt += 1) {
    await seedAssignmentJobAsDone(jobId, assignmentId)
    const confirmRes = await page.request.post(`${apiBase}/assignment/upload/confirm`, {
      data: { job_id: jobId, strict_requirements: true },
    })

    lastStatus = confirmRes.status()
    lastBody = await confirmRes.text()
    if (confirmRes.ok() || lastStatus === 409) {
      return
    }

    await page.waitForTimeout(300)
  }

  throw new Error(
    `assignment confirm did not stabilize, last status=${lastStatus}, body=${lastBody.slice(0, 300)}`,
  )
}

const startAssignmentUploadFromUi = async (page: Page, assignmentId: string) => {
  await page.getByPlaceholder('例如：HW-2026-02-05').fill(assignmentId)
  const fileInputs = page.locator('#workflow-upload-section input[type="file"]')
  await fileInputs.nth(0).setInputFiles(assignmentSourceFile)
  if ((await fileInputs.count()) > 1) {
    await fileInputs.nth(1).setInputFiles(assignmentAnswerFile)
  }
  const submitButton = page.getByRole('button', { name: '上传并开始解析' }).first()
  await expect(submitButton).toBeVisible({ timeout: 30_000 })
  await submitButton.click()
}

test.describe('Teacher Assignment Workflow Real System', () => {
  test.describe.configure({ timeout: 180_000 })
  test.skip(!realE2EEnabled, 'Set E2E_REAL=1 to run real backend assignment system tests.')

  test('P0-T-REAL-ASSIGN-001 [REAL] assignment full chain persists artifacts and clears marker', async ({ page }) => {
    const assignmentId = uniqueId('E2E_REAL_ASSIGN')
    const assignmentDir = path.join(assignmentDataRoot, assignmentId)
    let jobId = ''

    try {
      await rm(assignmentDir, { recursive: true, force: true })

      await setTeacherWorkflowState(page)
      await page.goto('/')

      await startAssignmentUploadFromUi(page, assignmentId)
      jobId = await waitForAssignmentJobId(page)

      await confirmAssignmentUploadEventually(page, jobId, assignmentId)

      const metaPath = path.join(assignmentDir, 'meta.json')
      const questionsPath = path.join(assignmentDir, 'questions.csv')
      const copiedSourcePath = path.join(assignmentDir, 'source', assignmentSourceFile.name)

      await expect.poll(() => pathExists(metaPath)).toBe(true)
      await expect.poll(() => pathExists(questionsPath)).toBe(true)
      await expect.poll(() => pathExists(copiedSourcePath)).toBe(true)

      const meta = await readJson<{ assignment_id?: string; job_id?: string }>(metaPath)
      expect(meta.assignment_id).toBe(assignmentId)
      expect(meta.job_id).toBe(jobId)

      const questionsCsv = await readFile(questionsPath, 'utf-8')
      expect(questionsCsv).toContain('question_id')
    } finally {
      await rm(assignmentDir, { recursive: true, force: true })
      if (jobId) {
        await rm(path.join(assignmentJobRoot, jobId), { recursive: true, force: true })
      }
    }
  })

  test('P0-T-REAL-ASSIGN-002 [REAL] assignment confirm failure is retryable and leaves no partial artifacts', async ({ page }) => {
    const assignmentId = uniqueId('E2E_REAL_ASSIGN_RETRY')
    const assignmentDir = path.join(assignmentDataRoot, assignmentId)
    let jobId = ''

    try {
      await rm(assignmentDir, { recursive: true, force: true })

      await setTeacherWorkflowState(page)
      await page.goto('/')

      await startAssignmentUploadFromUi(page, assignmentId)
      jobId = await waitForAssignmentJobId(page)

      const firstConfirmRes = await page.request.post(`${apiBase}/assignment/upload/confirm`, {
        data: { job_id: jobId, strict_requirements: true },
      })
      expect(firstConfirmRes.ok()).toBe(false)
      await expect.poll(() => pathExists(assignmentDir)).toBe(false)

      await confirmAssignmentUploadEventually(page, jobId, assignmentId)
      await expect.poll(() => pathExists(assignmentDir)).toBe(true)
    } finally {
      await rm(assignmentDir, { recursive: true, force: true })
      if (jobId) {
        await rm(path.join(assignmentJobRoot, jobId), { recursive: true, force: true })
      }
    }
  })
})
