import { expect } from '@playwright/test'
import type { MatrixCase, MatrixCaseRunner } from './helpers/e2eMatrixCases'
import { registerMatrixCases } from './helpers/e2eMatrixCases'
import {
  TEACHER_COMPOSER_PLACEHOLDER,
  openTeacherApp,
  setupBasicTeacherApiMocks,
  setupTeacherState,
} from './helpers/teacherHarness'

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

const buildAssignmentDraft = (jobId: string, assignmentId: string, missing: string[] = []) => ({
  job_id: jobId,
  assignment_id: assignmentId,
  date: '2026-02-08',
  scope: 'public',
  delivery_mode: 'pdf',
  requirements: {
    subject: '物理',
    topic: missing.includes('topic') ? '' : '电场强度',
    grade_level: '高二',
    class_level: '中等',
    core_concepts: ['电场'],
    typical_problem: '受力分析',
    misconceptions: missing.includes('misconceptions') ? [] : ['方向错误', '单位混乱', '漏条件', '乱代数'],
    duration_minutes: 40,
    preferences: ['分层训练'],
    extra_constraints: '',
  },
  requirements_missing: missing,
  questions: [{ id: 1, stem: '题干示例' }],
  draft_saved: true,
})

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
    default_max_score_qids: ['Q2'],
  },
  totals_summary: {
    avg_total: 71,
    median_total: 72,
    max_total_observed: 90,
  },
})

const skillWorkbenchCases: MatrixCase[] = [
  {
    id: 'C001',
    priority: 'P1',
    title: 'Skill search filters by id title and description',
    given: 'Skill catalog is loaded',
    when: 'Enter search text in skill filter',
    then: 'Only matching skills remain visible',
  },
  {
    id: 'C002',
    priority: 'P1',
    title: 'Favorites-only mode keeps insertion target stable',
    given: 'At least one skill is favorited',
    when: 'Enable favorites-only and insert token',
    then: 'Inserted token belongs to selected favorite skill',
  },
  {
    id: 'C003',
    priority: 'P1',
    title: 'Favorite state persists after reload',
    given: 'Favorite state was changed',
    when: 'Reload page',
    then: 'Favorite selections are restored from storage',
  },
  {
    id: 'C004',
    priority: 'P0',
    title: 'Pin current skill sends explicit skill_id',
    given: 'Skill card supports pin current',
    when: 'Pin and send message',
    then: 'Payload includes selected skill_id',
  },
  {
    id: 'C005',
    priority: 'P0',
    title: 'Auto-route mode omits skill_id',
    given: 'Current mode is pinned skill',
    when: 'Switch to auto-route and send message',
    then: 'Payload does not include skill_id',
  },
  {
    id: 'C006',
    priority: 'P1',
    title: 'Insert token uses current caret position',
    given: 'Caret is in middle of composer text',
    when: 'Click insert skill token',
    then: 'Token is inserted at caret position',
  },
  {
    id: 'C007',
    priority: 'P1',
    title: 'Use template appends and remains editable',
    given: 'Skill has at least one template prompt',
    when: 'Click use template',
    then: 'Template is inserted and composer remains editable',
  },
  {
    id: 'C008',
    priority: 'P1',
    title: 'Skills API failure falls back to bundled catalog',
    given: '/skills request fails',
    when: 'Open teacher app',
    then: 'Bundled skill list renders and chat still works',
  },
  {
    id: 'C009',
    priority: 'P1',
    title: 'Manual refresh toggles loading state correctly',
    given: 'Workbench shows refresh control',
    when: 'Click refresh skills',
    then: 'Control enters loading and re-enables on completion',
  },
  {
    id: 'C010',
    priority: 'P2',
    title: 'Collapse and expand preserves active tab',
    given: 'Active tab is workflow or skills',
    when: 'Collapse and reopen workbench',
    then: 'Previously active tab remains selected',
  },
  {
    id: 'C011',
    priority: 'P1',
    title: 'Agent card insertion sets matching agent_id',
    given: 'Agent card can insert @ token',
    when: 'Insert and send prompt',
    then: 'Payload agent_id matches inserted agent token',
  },
  {
    id: 'C012',
    priority: 'P1',
    title: 'Card insert and manual tokens produce coherent payload',
    given: 'User mixes card insertion and manual typing',
    when: 'Send prompt',
    then: 'Effective agent and skill selection is deterministic',
  },
]

const assignmentWorkflowCases: MatrixCase[] = [
  {
    id: 'D001',
    priority: 'P0',
    title: 'Assignment id is required before upload start',
    given: 'Workflow mode is assignment',
    when: 'Submit without assignment id',
    then: 'Validation blocks request to /assignment/upload/start',
  },
  {
    id: 'D002',
    priority: 'P0',
    title: 'Assignment files are required before upload start',
    given: 'Assignment id is provided',
    when: 'Submit without files',
    then: 'Validation blocks request and shows error',
  },
  {
    id: 'D003',
    priority: 'P0',
    title: 'Class scope requires class_name',
    given: 'Assignment scope is class',
    when: 'Submit with files but no class name',
    then: 'Validation blocks request and shows class requirement',
  },
  {
    id: 'D004',
    priority: 'P0',
    title: 'Student scope requires student_ids',
    given: 'Assignment scope is student',
    when: 'Submit with files but no student ids',
    then: 'Validation blocks request and shows student requirement',
  },
  {
    id: 'D005',
    priority: 'P1',
    title: 'Upload success writes active assignment job marker',
    given: '/assignment/upload/start returns job_id',
    when: 'Submit valid assignment upload',
    then: 'teacherActiveUpload is set with assignment job id',
  },
  {
    id: 'D006',
    priority: 'P1',
    title: 'Queued processing done states map to workflow chips',
    given: 'Status endpoint returns queued then processing then done',
    when: 'Polling runs',
    then: 'Workflow chips transition through expected labels',
  },
  {
    id: 'D007',
    priority: 'P0',
    title: 'Failed assignment status clears active upload marker',
    given: 'Active assignment upload exists',
    when: 'Status returns failed',
    then: 'Error is shown and teacherActiveUpload is cleared',
  },
  {
    id: 'D008',
    priority: 'P0',
    title: 'Draft save clears dirty markers',
    given: 'Assignment draft has local edits',
    when: 'Click save draft',
    then: 'Dirty flags clear and save confirmation appears',
  },
  {
    id: 'D009',
    priority: 'P0',
    title: 'Missing requirements disable confirm with reason',
    given: 'Draft includes requirements_missing fields',
    when: 'View confirm action',
    then: 'Confirm button is disabled with explanatory title',
  },
  {
    id: 'D010',
    priority: 'P0',
    title: 'Confirm action is duplicate-safe',
    given: 'Assignment confirm is available',
    when: 'Click confirm multiple times quickly',
    then: 'Exactly one /assignment/upload/confirm request is sent',
  },
  {
    id: 'D011',
    priority: 'P0',
    title: 'Successful confirm enters created terminal state',
    given: '/assignment/upload/confirm returns success',
    when: 'Click confirm',
    then: 'UI shows created state and clears active upload marker',
  },
  {
    id: 'D012',
    priority: 'P1',
    title: 'job_not_ready response preserves draft context',
    given: '/assignment/upload/confirm returns job_not_ready',
    when: 'Click confirm',
    then: 'Draft data remains and retry guidance is shown',
  },
  {
    id: 'D013',
    priority: 'P1',
    title: 'Refresh restores assignment polling from local marker',
    given: 'teacherActiveUpload has assignment job id',
    when: 'Reload page',
    then: 'Workflow resumes polling and reloads draft state',
  },
  {
    id: 'D014',
    priority: 'P1',
    title: 'Request body preserves files and answer_files fields',
    given: 'Upload includes files and answer_files',
    when: 'Submit assignment upload',
    then: 'Multipart payload includes all expected file fields',
  },
]

const examWorkflowCases: MatrixCase[] = [
  {
    id: 'E001',
    priority: 'P0',
    title: 'Exam upload requires paper files',
    given: 'Workflow mode is exam',
    when: 'Submit without paper files',
    then: 'Validation blocks request to /exam/upload/start',
  },
  {
    id: 'E002',
    priority: 'P0',
    title: 'Exam upload requires score files',
    given: 'Paper files are selected',
    when: 'Submit without score files',
    then: 'Validation blocks request and shows score file requirement',
  },
  {
    id: 'E003',
    priority: 'P1',
    title: 'Exam upload success writes active job marker',
    given: '/exam/upload/start returns job_id',
    when: 'Submit valid exam upload',
    then: 'teacherActiveUpload is set with exam job id',
  },
  {
    id: 'E004',
    priority: 'P1',
    title: 'Progress values update in legal sequence',
    given: 'Status endpoint returns progress updates',
    when: 'Polling runs to completion',
    then: 'Progress is non-negative and never regresses unexpectedly',
  },
  {
    id: 'E005',
    priority: 'P0',
    title: 'Edited exam draft fields round-trip correctly',
    given: 'Exam draft is loaded',
    when: 'Edit and save date class and max score then reload draft',
    then: 'Saved values persist exactly',
  },
  {
    id: 'E006',
    priority: 'P0',
    title: 'Exam confirm success shows summary outputs',
    given: '/exam/upload/confirm returns success',
    when: 'Click confirm',
    then: 'UI displays exam id and question count summary',
  },
  {
    id: 'E007',
    priority: 'P0',
    title: 'Confirmed exam status clears active upload marker',
    given: 'Active exam upload exists',
    when: 'Status returns confirmed',
    then: 'teacherActiveUpload is removed',
  },
  {
    id: 'E008',
    priority: 'P0',
    title: 'Failed exam status leaves clear diagnostic message',
    given: 'Active exam upload exists',
    when: 'Status returns failed',
    then: 'Failure reason is visible and workflow is recoverable',
  },
  {
    id: 'E009',
    priority: 'P1',
    title: 'Server-generated exam id is displayed when omitted',
    given: 'Client submits without exam_id',
    when: 'Upload starts successfully',
    then: 'Generated exam id is shown in UI',
  },
  {
    id: 'E010',
    priority: 'P1',
    title: 'Mixed score sources still create exam job',
    given: 'Score upload includes xlsx and image files',
    when: 'Submit exam upload',
    then: 'Job is created and enters processing',
  },
  {
    id: 'E011',
    priority: 'P1',
    title: 'Confirm remains disabled before parse done',
    given: 'Exam parse status is queued or processing',
    when: 'Inspect confirm action',
    then: 'Confirm control stays disabled',
  },
  {
    id: 'E012',
    priority: 'P1',
    title: 'Exam not-ready confirm response preserves context',
    given: '/exam/upload/confirm returns job_not_ready',
    when: 'Click confirm',
    then: 'Draft and status context remain for retry',
  },
  {
    id: 'E013',
    priority: 'P1',
    title: 'Assignment and exam forms keep isolated state',
    given: 'Both workflow forms have unsaved values',
    when: 'Switch between assignment and exam modes',
    then: 'Each form restores its own values only',
  },
  {
    id: 'E014',
    priority: 'P2',
    title: 'Collapsed workflow summary reflects active job only',
    given: 'Upload panel supports collapsed summary',
    when: 'Switch active jobs and collapse panel',
    then: 'Summary always shows latest active job metadata',
  },
]

const implementations: Partial<Record<string, MatrixCaseRunner>> = {
  C004: async ({ page }) => {
    const { chatStartCalls } = await openTeacherApp(page)

    const homeworkSkillCard = page
      .locator('.skill-card')
      .filter({ has: page.getByText('作业生成') })
      .first()

    await homeworkSkillCard.getByRole('button', { name: '设为当前' }).click()
    await page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER).fill('固定技能请求')
    await page.getByRole('button', { name: '发送' }).click()

    await expect.poll(() => chatStartCalls.length).toBe(1)
    expect(chatStartCalls[0].skill_id).toBe('physics-homework-generator')
  },

  C005: async ({ page }) => {
    const { chatStartCalls } = await openTeacherApp(page)

    const homeworkSkillCard = page
      .locator('.skill-card')
      .filter({ has: page.getByText('作业生成') })
      .first()

    await homeworkSkillCard.getByRole('button', { name: '设为当前' }).click()
    await page.getByRole('button', { name: '使用自动路由' }).click()

    await page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER).fill('自动路由请求')
    await page.getByRole('button', { name: '发送' }).click()

    await expect.poll(() => chatStartCalls.length).toBe(1)
    const payload = chatStartCalls[0] as Record<string, unknown>
    expect(Object.prototype.hasOwnProperty.call(payload, 'skill_id')).toBe(false)
  },

  D001: async ({ page }) => {
    let uploadCalls = 0
    await openTeacherApp(page, { stateOverrides: { teacherWorkbenchTab: 'workflow' } })

    await page.route('http://localhost:8000/assignment/upload/start', async (route) => {
      uploadCalls += 1
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
    })

    await page.locator('#workflow-upload-section form.upload-form button[type="submit"]').click()
    await expect(page.getByText('请填写作业编号')).toBeVisible()
    expect(uploadCalls).toBe(0)
  },

  D002: async ({ page }) => {
    let uploadCalls = 0
    await openTeacherApp(page, { stateOverrides: { teacherWorkbenchTab: 'workflow' } })

    await page.route('http://localhost:8000/assignment/upload/start', async (route) => {
      uploadCalls += 1
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
    })

    await page.getByPlaceholder('例如：HW-2026-02-05').fill('HW-P0-002')
    await page.locator('#workflow-upload-section form.upload-form button[type="submit"]').click()

    await expect(page.getByText('请至少上传一份作业文件（文档或图片）')).toBeVisible()
    expect(uploadCalls).toBe(0)
  },

  D003: async ({ page }) => {
    let uploadCalls = 0
    await openTeacherApp(page, { stateOverrides: { teacherWorkbenchTab: 'workflow' } })

    await page.route('http://localhost:8000/assignment/upload/start', async (route) => {
      uploadCalls += 1
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
    })

    await page.getByPlaceholder('例如：HW-2026-02-05').fill('HW-P0-003')
    await page.locator('#workflow-upload-section form.upload-form select').first().selectOption('class')
    await page.locator('#workflow-upload-section input[type="file"]').first().setInputFiles(fakePdfFile)
    await page.locator('#workflow-upload-section form.upload-form button[type="submit"]').click()

    await expect(page.getByText('班级作业请填写班级')).toBeVisible()
    expect(uploadCalls).toBe(0)
  },

  D004: async ({ page }) => {
    let uploadCalls = 0
    await openTeacherApp(page, { stateOverrides: { teacherWorkbenchTab: 'workflow' } })

    await page.route('http://localhost:8000/assignment/upload/start', async (route) => {
      uploadCalls += 1
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
    })

    await page.getByPlaceholder('例如：HW-2026-02-05').fill('HW-P0-004')
    await page.locator('#workflow-upload-section form.upload-form select').first().selectOption('student')
    await page.locator('#workflow-upload-section input[type="file"]').first().setInputFiles(fakePdfFile)
    await page.locator('#workflow-upload-section form.upload-form button[type="submit"]').click()

    await expect(page.getByText('私人作业请填写学生编号')).toBeVisible()
    expect(uploadCalls).toBe(0)
  },

  D007: async ({ page }) => {
    const jobId = 'job_assignment_failed_p0'

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
        body: JSON.stringify({ job_id: jobId, status: 'failed', error: '解析失败' }),
      })
    })

    await page.goto('/')
    await expect(page.locator('.workflow-chip.error')).toHaveText('解析失败')
    await expect.poll(async () => page.evaluate(() => localStorage.getItem('teacherActiveUpload'))).toBeNull()
  },

  D008: async ({ page }) => {
    const jobId = 'job_assignment_save_p0'
    let savePayload: any = null

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
          assignment_id: 'HW-P0-SAVE',
          requirements_missing: [],
        }),
      })
    })

    await page.route('http://localhost:8000/assignment/upload/draft**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, draft: buildAssignmentDraft(jobId, 'HW-P0-SAVE') }),
      })
    })

    await page.route('http://localhost:8000/assignment/upload/draft/save', async (route) => {
      savePayload = JSON.parse(route.request().postData() || '{}')
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, message: '草稿已保存。' }),
      })
    })

    await page.goto('/')

    await page.getByDisplayValue('电场强度').fill('电场综合')
    await page.getByRole('button', { name: '保存草稿' }).click()

    await expect.poll(() => savePayload).not.toBeNull()
    expect(savePayload?.requirements?.topic).toBe('电场综合')
    await expect(page.getByText('草稿已保存。')).toBeVisible()
  },

  D009: async ({ page }) => {
    const jobId = 'job_assignment_missing_p0'
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
          assignment_id: 'HW-P0-MISSING',
          requirements_missing: ['topic', 'misconceptions'],
        }),
      })
    })

    await page.route('http://localhost:8000/assignment/upload/draft**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, draft: buildAssignmentDraft(jobId, 'HW-P0-MISSING', ['topic', 'misconceptions']) }),
      })
    })

    await page.route('http://localhost:8000/assignment/upload/confirm', async (route) => {
      confirmCalls += 1
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
    })

    await page.goto('/')

    const confirmBtn = page.locator('.confirm-btn')
    await expect(confirmBtn).toBeDisabled()
    await expect(confirmBtn).toHaveAttribute('title', /请先补全/)
    await confirmBtn.evaluate((node) => (node as HTMLButtonElement).click())
    expect(confirmCalls).toBe(0)
  },

  D010: async ({ page }) => {
    const jobId = 'job_assignment_confirming_p0'
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
          assignment_id: 'HW-P0-CONFIRMING',
          requirements_missing: [],
        }),
      })
    })

    await page.route('http://localhost:8000/assignment/upload/draft**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, draft: buildAssignmentDraft(jobId, 'HW-P0-CONFIRMING') }),
      })
    })

    await page.route('http://localhost:8000/assignment/upload/draft/save', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, message: '草稿已保存。' }) })
    })

    await page.route('http://localhost:8000/assignment/upload/confirm', async (route) => {
      confirmCalls += 1
      await new Promise((resolve) => setTimeout(resolve, 240))
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, assignment_id: 'HW-P0-CONFIRMING', question_count: 1 }),
      })
    })

    await page.goto('/')

    const confirmBtn = page.locator('.confirm-btn')
    await confirmBtn.click()
    await confirmBtn.evaluate((node) => (node as HTMLButtonElement).click())

    await expect.poll(() => confirmCalls).toBe(1)
  },

  D011: async ({ page }) => {
    const jobId = 'job_assignment_confirmed_p0'

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
          assignment_id: 'HW-P0-CONFIRMED',
          requirements_missing: [],
        }),
      })
    })

    await page.route('http://localhost:8000/assignment/upload/draft**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, draft: buildAssignmentDraft(jobId, 'HW-P0-CONFIRMED') }),
      })
    })

    await page.route('http://localhost:8000/assignment/upload/draft/save', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, message: '草稿已保存。' }) })
    })

    await page.route('http://localhost:8000/assignment/upload/confirm', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, assignment_id: 'HW-P0-CONFIRMED', question_count: 1 }),
      })
    })

    await page.goto('/')

    const confirmBtn = page.locator('.confirm-btn')
    await confirmBtn.click()

    await expect(confirmBtn).toHaveText('已创建')
    await expect.poll(async () => page.evaluate(() => localStorage.getItem('teacherActiveUpload'))).toBeNull()
  },

  E001: async ({ page }) => {
    let calls = 0
    await openTeacherApp(page, { stateOverrides: { teacherWorkbenchTab: 'workflow' } })

    await page.route('http://localhost:8000/exam/upload/start', async (route) => {
      calls += 1
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
    })

    await page.getByRole('button', { name: '考试', exact: true }).first().click()
    await page.locator('#workflow-upload-section form.upload-form button[type="submit"]').click()

    await expect(page.getByText('请至少上传一份试卷文件（文档或图片）')).toBeVisible()
    expect(calls).toBe(0)
  },

  E002: async ({ page }) => {
    let calls = 0
    await openTeacherApp(page, { stateOverrides: { teacherWorkbenchTab: 'workflow' } })

    await page.route('http://localhost:8000/exam/upload/start', async (route) => {
      calls += 1
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
    })

    await page.getByRole('button', { name: '考试', exact: true }).first().click()
    await page.locator('#workflow-upload-section input[type="file"]').first().setInputFiles(fakePdfFile)
    await page.locator('#workflow-upload-section form.upload-form button[type="submit"]').click()

    await expect(page.getByText('请至少上传一份成绩文件（表格文件或文档/图片）')).toBeVisible()
    expect(calls).toBe(0)
  },

  E005: async ({ page }) => {
    const jobId = 'job_exam_save_p0'
    let savePayload: any = null

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
        body: JSON.stringify({ job_id: jobId, status: 'done', progress: 100, exam_id: 'EX-P0-SAVE' }),
      })
    })

    await page.route('http://localhost:8000/exam/upload/draft**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, draft: buildExamDraft(jobId, 'EX-P0-SAVE') }),
      })
    })

    await page.route('http://localhost:8000/exam/upload/draft/save', async (route) => {
      savePayload = JSON.parse(route.request().postData() || '{}')
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, message: '考试草稿已保存。' }),
      })
    })

    await page.goto('/')

    const examSection = page.locator('#workflow-exam-draft-section')
    const metaCard = examSection.locator('.draft-card').first()

    await metaCard.locator('input').nth(0).fill('2026-02-10')
    await metaCard.locator('input').nth(1).fill('高二2404班')

    await examSection.getByRole('button', { name: '保存草稿' }).click()

    await expect.poll(() => savePayload).not.toBeNull()
    expect(savePayload?.meta?.date).toBe('2026-02-10')
    expect(savePayload?.meta?.class_name).toBe('高二2404班')
    await expect(page.getByText('考试草稿已保存。')).toBeVisible()
  },

  E006: async ({ page }) => {
    const jobId = 'job_exam_confirm_p0'

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
        body: JSON.stringify({ job_id: jobId, status: 'done', progress: 100, exam_id: 'EX-P0-CONFIRM' }),
      })
    })

    await page.route('http://localhost:8000/exam/upload/draft**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, draft: buildExamDraft(jobId, 'EX-P0-CONFIRM') }),
      })
    })

    await page.route('http://localhost:8000/exam/upload/draft/save', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, message: '考试草稿已保存。' }) })
    })

    await page.route('http://localhost:8000/exam/upload/confirm', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          message: '考试已确认创建。',
          exam_id: 'EX-P0-CONFIRM',
          question_count: 2,
        }),
      })
    })

    await page.goto('/')

    const examSection = page.locator('#workflow-exam-draft-section')
    await examSection.getByRole('button', { name: '创建考试' }).click()

    await expect(examSection.getByRole('button', { name: '已创建' })).toBeVisible()
    await expect(page.getByText('考试已确认创建。')).toBeVisible()
  },

  E007: async ({ page }) => {
    const jobId = 'job_exam_confirmed_p0'

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
        body: JSON.stringify({ job_id: jobId, status: 'confirmed', progress: 100, exam_id: 'EX-P0-CONFIRMED' }),
      })
    })

    await page.route('http://localhost:8000/exam/upload/draft**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, draft: buildExamDraft(jobId, 'EX-P0-CONFIRMED') }),
      })
    })

    await page.goto('/')

    await expect.poll(async () => page.evaluate(() => localStorage.getItem('teacherActiveUpload'))).toBeNull()
  },

  E008: async ({ page }) => {
    const jobId = 'job_exam_failed_p0'

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
        body: JSON.stringify({ job_id: jobId, status: 'failed', error: '解析失败' }),
      })
    })

    await page.goto('/')

    await expect(page.locator('.workflow-chip.error')).toHaveText('解析失败')
    await expect.poll(async () => page.evaluate(() => localStorage.getItem('teacherActiveUpload'))).toBeNull()
  },
}

registerMatrixCases('Teacher Skill Workbench', skillWorkbenchCases, implementations)
registerMatrixCases('Teacher Assignment Workflow', assignmentWorkflowCases, implementations)
registerMatrixCases('Teacher Exam Workflow', examWorkflowCases, implementations)
