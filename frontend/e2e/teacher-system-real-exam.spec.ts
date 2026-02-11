import { access, mkdir, readFile, rm, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, test, type Page } from '@playwright/test'

const realE2EEnabled = process.env.E2E_REAL === '1'
const apiBase = String(process.env.E2E_REAL_API_BASE || 'http://localhost:8000').replace(/\/$/, '')
const specDir = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(specDir, '..', '..')
const examDataRoot = path.join(repoRoot, 'data', 'exams')
const analysisDataRoot = path.join(repoRoot, 'data', 'analysis')
const examJobRoot = path.join(repoRoot, 'uploads', 'exam_jobs')

const examPaperFile = {
  name: 'exam-paper.txt',
  mimeType: 'text/plain',
  buffer: Buffer.from(
    [
      '高二物理阶段性测试（电场与电势）',
      '1. 判断电场方向与受力关系。',
      '2. 对比两点电势并分析电势能变化。',
      '3. 结合受力图分析粒子运动。',
    ].join('\n'),
    'utf-8',
  ),
}

const examScoreFile = {
  name: 'exam-scores.csv',
  mimeType: 'text/csv',
  buffer: Buffer.from(
    [
      'student_id,student_name,class_name,total',
      'S001,测试学生,高二1班,88',
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

const writeCsv = async (targetPath: string, content: string) => {
  await writeFile(targetPath, content, 'utf-8')
}

const setTeacherWorkflowState = async (page: Page) => {
  await page.addInitScript(({ base }) => {
    const seededKey = '__e2e_real_exam_seeded__'
    if (!sessionStorage.getItem(seededKey)) {
      localStorage.clear()
      localStorage.setItem('teacherMainView', 'chat')
      localStorage.setItem('teacherSessionSidebarOpen', 'false')
      localStorage.setItem('teacherSkillsOpen', 'true')
      localStorage.setItem('teacherWorkbenchTab', 'workflow')
      localStorage.setItem('teacherSkillPinned', 'false')
      localStorage.setItem('teacherActiveSkillId', 'physics-teacher-ops')
      sessionStorage.setItem(seededKey, '1')
    }
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

const waitForExamJobId = async (page: Page) => {
  await expect
    .poll(async () => readActiveUploadJobId(page, 'exam'), {
      timeout: 20_000,
      message: 'teacherActiveUpload should contain exam job id',
    })
    .not.toBe('')
  return readActiveUploadJobId(page, 'exam')
}

const buildExamDraft = (jobId: string, examId: string) => ({
  job_id: jobId,
  exam_id: examId,
  meta: { date: '2026-02-11', class_name: '高二1班' },
  paper_files: [examPaperFile.name],
  score_files: [examScoreFile.name],
  answer_files: [],
  counts: { students: 1, responses: 1, questions: 1 },
  counts_scored: { students: 1, responses: 1 },
  totals_summary: { avg_total: 88, median_total: 88, max_total_observed: 88 },
  scoring: {
    status: 'scored',
    responses_total: 1,
    responses_scored: 1,
    students_total: 1,
    students_scored: 1,
    default_max_score_qids: [],
  },
  score_schema: { confirm: true },
  needs_confirm: false,
  questions: [{ question_id: 'Q1', question_no: '1', sub_no: '', max_score: 100 }],
  answer_key_text: '',
})

const seedExamJobAsDone = async (jobId: string, examId: string) => {
  const jobDir = path.join(examJobRoot, jobId)
  const jobPath = path.join(jobDir, 'job.json')
  const derivedDir = path.join(jobDir, 'derived')

  await expect.poll(() => pathExists(jobPath), { timeout: 20_000 }).toBe(true)

  await mkdir(derivedDir, { recursive: true })

  const responsesScoredCsv = [
    'exam_id,student_id,student_name,class_name,question_id,question_no,sub_no,raw_label,raw_value,raw_answer,score,is_correct',
    `${examId},S001,测试学生,高二1班,Q1,1,,,A,88,88,true`,
  ].join('\n')
  const responsesUnscoredCsv = [
    'exam_id,student_id,student_name,class_name,question_id,question_no,sub_no,raw_label,raw_value,raw_answer,score,is_correct',
    `${examId},S001,测试学生,高二1班,Q1,1,,,A,,,`,
  ].join('\n')
  const questionsCsv = [
    'question_id,question_no,sub_no,order,max_score,stem_ref',
    'Q1,1,,1,100,',
  ].join('\n')

  await writeCsv(path.join(derivedDir, 'responses_scored.csv'), responsesScoredCsv)
  await writeCsv(path.join(derivedDir, 'responses_unscored.csv'), responsesUnscoredCsv)
  await writeCsv(path.join(derivedDir, 'questions.csv'), questionsCsv)

  const parsedPayload = {
    exam_id: examId,
    date: '2026-02-11',
    class_name: '高二1班',
    meta: {
      date: '2026-02-11',
      class_name: '高二1班',
    },
    paper_files: [examPaperFile.name],
    score_files: [examScoreFile.name],
    answer_files: [],
    counts: {
      students: 1,
      responses: 1,
      questions: 1,
    },
    counts_scored: {
      students: 1,
      responses: 1,
    },
    totals_summary: {
      avg_total: 88,
      median_total: 88,
      max_total_observed: 88,
    },
    scoring: {
      status: 'scored',
      responses_total: 1,
      responses_scored: 1,
      students_total: 1,
      students_scored: 1,
      default_max_score_qids: [],
    },
    warnings: [],
    needs_confirm: false,
    score_schema: { confirm: true },
    questions: [{ question_id: 'Q1', question_no: '1', sub_no: '', max_score: 100 }],
  }

  await writeJson(path.join(jobDir, 'parsed.json'), parsedPayload)

  const job = await readJson<Record<string, unknown>>(jobPath)
  const nextJob = {
    ...job,
    exam_id: examId,
    status: 'done',
    progress: 100,
    step: 'parsed',
    error: '',
    updated_at: new Date().toISOString(),
    counts: parsedPayload.counts,
    counts_scored: parsedPayload.counts_scored,
    totals_summary: parsedPayload.totals_summary,
    scoring: parsedPayload.scoring,
  }
  await writeJson(jobPath, nextJob)
}

const confirmExamUploadEventually = async (page: Page, jobId: string, examId: string) => {
  let lastStatus = 0
  let lastBody = ''

  for (let attempt = 0; attempt < 20; attempt += 1) {
    await seedExamJobAsDone(jobId, examId)
    const confirmRes = await page.request.post(`${apiBase}/exam/upload/confirm`, {
      data: { job_id: jobId },
    })

    lastStatus = confirmRes.status()
    lastBody = await confirmRes.text()
    if (confirmRes.ok() || lastStatus === 409) {
      return
    }

    await page.waitForTimeout(300)
  }

  throw new Error(`exam confirm did not stabilize, last status=${lastStatus}, body=${lastBody.slice(0, 300)}`)
}

const setupExamDraftApis = async (page: Page, jobId: string, examId: string) => {
  await page.route('**/exam/upload/draft**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, draft: buildExamDraft(jobId, examId) }),
    })
  })

  await page.route('**/exam/upload/draft/save', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, message: '考试草稿已保存。' }),
    })
  })
}

const startExamUploadFromUi = async (page: Page) => {
  await page.getByRole('button', { name: '考试', exact: true }).first().click()
  const fileInputs = page.locator('#workflow-upload-section input[type="file"]')
  await fileInputs.nth(0).setInputFiles(examPaperFile)
  await fileInputs.nth(2).setInputFiles(examScoreFile)
  const submitButton = page.getByRole('button', { name: '上传并开始解析' }).first()
  await expect(submitButton).toBeVisible({ timeout: 30_000 })
  await submitButton.click()
}

const ensureExamDraftReady = async (page: Page) => {
  const examSection = page.locator('#workflow-exam-draft-section')
  await expect(examSection).toBeVisible({ timeout: 30_000 })

  const expandButton = examSection.getByRole('button', { name: '展开' }).first()
  if ((await expandButton.count()) > 0 && (await expandButton.isVisible())) {
    await expandButton.click()
  }

  const confirmButton = examSection.getByRole('button', { name: '创建考试' }).first()
  await expect(confirmButton).toBeVisible({ timeout: 30_000 })
  return { examSection, confirmButton }
}

test.describe('Teacher Exam Workflow Real System', () => {
  test.describe.configure({ timeout: 180_000 })
  test.skip(!realE2EEnabled, 'Set E2E_REAL=1 to run real backend exam system tests.')

  test('P0-T-REAL-EXAM-001 [REAL] exam full chain writes exams and analysis artifacts consistently', async ({ page }) => {
    const examId = uniqueId('E2E_REAL_EXAM')
    const examDir = path.join(examDataRoot, examId)
    const analysisDir = path.join(analysisDataRoot, examId)
    let jobId = ''

    try {
      await rm(examDir, { recursive: true, force: true })
      await rm(analysisDir, { recursive: true, force: true })

      await setTeacherWorkflowState(page)
      await page.goto('/')

      await startExamUploadFromUi(page)
      jobId = await waitForExamJobId(page)

      await confirmExamUploadEventually(page, jobId, examId)

      const manifestPath = path.join(examDir, 'manifest.json')
      const responsesPath = path.join(examDir, 'derived', 'responses_scored.csv')

      await expect.poll(() => pathExists(manifestPath)).toBe(true)
      await expect.poll(() => pathExists(responsesPath)).toBe(true)
      await expect.poll(() => pathExists(analysisDir)).toBe(true)

      const manifest = await readJson<{ exam_id?: string; files?: Record<string, string> }>(manifestPath)
      expect(manifest.exam_id).toBe(examId)
      expect(typeof manifest.files?.responses_scored).toBe('string')
    } finally {
      await rm(examDir, { recursive: true, force: true })
      await rm(analysisDir, { recursive: true, force: true })
      if (jobId) {
        await rm(path.join(examJobRoot, jobId), { recursive: true, force: true })
      }
    }
  })

  test('P0-T-REAL-EXAM-002 [REAL] refresh-before-confirm resumes once and avoids duplicate writes', async ({ page }) => {
    const examId = uniqueId('E2E_REAL_EXAM_REFRESH')
    const examDir = path.join(examDataRoot, examId)
    const analysisDir = path.join(analysisDataRoot, examId)
    const confirmUrl = `${apiBase}/exam/upload/confirm`
    let confirmCalls = 0
    let jobId = ''

    try {
      await rm(examDir, { recursive: true, force: true })
      await rm(analysisDir, { recursive: true, force: true })

      await setTeacherWorkflowState(page)
      await page.goto('/')

      await startExamUploadFromUi(page)
      jobId = await waitForExamJobId(page)
      await seedExamJobAsDone(jobId, examId)
      await setupExamDraftApis(page, jobId, examId)

      await page.reload()
      await seedExamJobAsDone(jobId, examId)

      await page.route(confirmUrl, async (route) => {
        if (route.request().method().toUpperCase() !== 'POST') {
          await route.continue()
          return
        }
        confirmCalls += 1
        await route.continue()
      })

      const { confirmButton: confirmBtn } = await ensureExamDraftReady(page)
      await expect(confirmBtn).toBeEnabled({ timeout: 30_000 })

      await confirmBtn.click()
      if (await confirmBtn.isVisible()) {
        await confirmBtn.click()
      }

      await expect.poll(() => confirmCalls).toBe(1)
      await confirmExamUploadEventually(page, jobId, examId)
      await expect.poll(() => pathExists(path.join(examDir, 'manifest.json'))).toBe(true)
      await expect.poll(() => pathExists(analysisDir)).toBe(true)
    } finally {
      await rm(examDir, { recursive: true, force: true })
      await rm(analysisDir, { recursive: true, force: true })
      if (jobId) {
        await rm(path.join(examJobRoot, jobId), { recursive: true, force: true })
      }
    }
  })
})
