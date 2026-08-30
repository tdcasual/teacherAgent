import { expect, test } from '@playwright/test'
import type { MatrixCase, MatrixCaseRunner } from './helpers/e2eMatrixCases'
import { registerMatrixCases } from './helpers/e2eMatrixCases'
import {
  TEACHER_COMPOSER_PLACEHOLDER,
  openTeacherApp,
  setupBasicTeacherApiMocks,
  setupTeacherState,
} from './helpers/teacherHarness'
import {
  assignmentConfirmButton,
  workflowAssignmentScopeSelect,
  workflowStatusChip,
  workflowUploadSection,
  workflowUploadSubmitButton,
} from './helpers/workflowLocators'

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
    title: 'Skill card insertion sets matching skill',
    given: 'Skill card can insert $ token',
    when: 'Insert and send prompt',
    then: 'Payload skill_id matches inserted skill token',
  },
  {
    id: 'C012',
    priority: 'P1',
    title: 'Card insert and manual tokens produce coherent payload',
    given: 'User mixes card insertion and manual typing',
    when: 'Send prompt',
    then: 'Effective skill selection is deterministic',
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


const implementations: Partial<Record<string, MatrixCaseRunner>> = {
  C001: async ({ page }) => {
    await openTeacherApp(page)
    const search = page.getByPlaceholder('搜索教学能力')

    await search.fill('作业')
    await expect(page.locator('.skill-card')).toHaveCount(1)
    await expect(page.locator('.skill-card').first()).toContainText('作业生成')

    await search.fill('teacher-assignment-ops')
    await expect(page.locator('.skill-card')).toHaveCount(1)
    await expect(page.locator('.skill-card').first()).toContainText('教学运营')

    await search.fill('运营流程')
    await expect(page.locator('.skill-card')).toHaveCount(1)
    await expect(page.locator('.skill-card').first()).toContainText('教学运营')
  },

  C002: async ({ page }) => {
    await openTeacherApp(page)
    const composer = page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER)
    const homeworkSkillCard = page.locator('.skill-card').filter({ has: page.getByText('作业生成') }).first()

    await homeworkSkillCard.getByLabel('收藏能力').click()
    await page.getByLabel('只看收藏').check()
    await expect(page.locator('.skill-card')).toHaveCount(1)
    await expect(page.locator('.skill-card').first()).toContainText('作业生成')

    await homeworkSkillCard.getByRole('button', { name: '插入 $' }).click()
    await expect(composer).toHaveValue(/\$homework-generator/)
  },

  C003: async ({ page }) => {
    await openTeacherApp(page, { clearLocalStorage: false })
    const homeworkSkillCard = page.locator('.skill-card').filter({ has: page.getByText('作业生成') }).first()
    await homeworkSkillCard.getByLabel('收藏能力').click()
    await expect
      .poll(async () => page.evaluate(() => JSON.parse(localStorage.getItem('teacherSkillFavorites') || '[]')))
      .toContain('homework-generator')

    await page.reload()
    await expect
      .poll(async () => page.evaluate(() => JSON.parse(localStorage.getItem('teacherSkillFavorites') || '[]')))
      .toContain('homework-generator')
    await page.getByLabel('只看收藏').check()

    await expect(page.locator('.skill-card')).toHaveCount(1)
    await expect(page.locator('.skill-card').first()).toContainText('作业生成')
  },

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
    expect(chatStartCalls[0].skill_id).toBe('homework-generator')
  },

  C005: async ({ page }) => {
    const { chatStartCalls } = await openTeacherApp(page)

    const homeworkSkillCard = page
      .locator('.skill-card')
      .filter({ has: page.getByText('作业生成') })
      .first()

    await homeworkSkillCard.getByRole('button', { name: '设为当前' }).click()
    await page.getByRole('button', { name: '切回自动推荐' }).click()

    await page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER).fill('自动路由请求')
    await page.getByRole('button', { name: '发送' }).click()

    await expect.poll(() => chatStartCalls.length).toBe(1)
    const payload = chatStartCalls[0] as Record<string, unknown>
    expect(Object.prototype.hasOwnProperty.call(payload, 'skill_id')).toBe(false)
  },

  C006: async ({ page }) => {
    await openTeacherApp(page)
    const composer = page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER)
    const homeworkSkillCard = page.locator('.skill-card').filter({ has: page.getByText('作业生成') }).first()

    await composer.fill('alpha beta')
    await composer.focus()
    await composer.press('ArrowLeft')
    await composer.press('ArrowLeft')
    await composer.press('ArrowLeft')
    await composer.press('ArrowLeft')
    await homeworkSkillCard.getByRole('button', { name: '插入 $' }).click()

    await expect(composer).toHaveValue('alpha $homework-generator beta')
  },

  C007: async ({ page }) => {
    await openTeacherApp(page)
    const composer = page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER)
    const homeworkSkillCard = page.locator('.skill-card').filter({ has: page.getByText('作业生成') }).first()

    await composer.fill('前缀')
    await homeworkSkillCard.getByRole('button', { name: '使用模板' }).first().click()

    const templated = (await composer.inputValue()).trim()
    expect(templated.startsWith('前缀')).toBe(true)
    expect(templated.length).toBeGreaterThan('前缀'.length)

    await composer.fill(`${templated} 可编辑`)
    expect(await composer.inputValue()).toContain('可编辑')
  },

  C008: async ({ page }) => {
    const startCalls: Array<Record<string, unknown>> = []
    await setupTeacherState(page)
    await setupBasicTeacherApiMocks(page)
    await page.route('http://localhost:8000/skills', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'skills api down' }),
      })
    })
    await page.route('http://localhost:8000/chat/start', async (route) => {
      startCalls.push(JSON.parse(route.request().postData() || '{}'))
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          job_id: 'job_c008',
          status: 'done',
          reply: '回执：fallback skills 仍可发送',
          lane_queue_position: 0,
          lane_queue_size: 1,
        }),
      })
    })
    await page.route('http://localhost:8000/chat/status**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ job_id: 'job_c008', status: 'done', reply: '回执：fallback skills 仍可发送' }),
      })
    })

    await page.goto('/')
    await expect(page.getByText('状态码 500')).toBeVisible()
    await expect(page.locator('.skill-card').filter({ hasText: '作业生成' }).first()).toBeVisible()

    await page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER).fill('fallback skills 仍可发送')
    await page.getByRole('button', { name: '发送' }).click()
    await expect(page.locator('.messages').getByText('回执：fallback skills 仍可发送')).toBeVisible()
    await expect.poll(() => startCalls.length).toBe(1)
  },

  C009: async ({ page }) => {
    let skillsCalls = 0
    await setupTeacherState(page)
    await setupBasicTeacherApiMocks(page)
    await page.route('http://localhost:8000/skills', async (route) => {
      skillsCalls += 1
      await page.waitForTimeout(180)
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          skills: [
            {
              id: 'teacher-assignment-ops',
              title: '教学运营',
              desc: '老师运营流程',
              prompts: ['请总结班级学习情况'],
              examples: ['查看班级趋势'],
              allowed_roles: ['teacher'],
            },
            {
              id: 'homework-generator',
              title: '作业生成',
              desc: '生成分层作业',
              prompts: ['生成静电场作业'],
              examples: ['高二静电场 8 题'],
              allowed_roles: ['teacher'],
            },
          ],
        }),
      })
    })

    await page.goto('/')
    const refreshBtn = page.locator('.skills-panel .skills-header').getByRole('button', { name: '刷新' })
    await refreshBtn.click()

    await expect(refreshBtn).toBeDisabled()
    await expect.poll(() => skillsCalls).toBeGreaterThan(1)
    await expect(refreshBtn).toBeEnabled()
  },

  C010: async ({ page }) => {
    await openTeacherApp(page)
    const workflowTab = page.getByRole('button', { name: '工作流', exact: true }).first()
    const skillTab = page.getByRole('button', { name: '能力', exact: true }).first()

    await workflowTab.click()
    await expect(workflowTab).toHaveClass(/active/)

    await page.getByRole('button', { name: '收起工作台' }).click()
    await expect(page.getByRole('button', { name: '打开工作台' })).toBeVisible()
    await page.getByRole('button', { name: '打开工作台' }).click()
    await expect(workflowTab).toHaveClass(/active/)

    await skillTab.click()
    await expect(skillTab).toHaveClass(/active/)
    await page.getByRole('button', { name: '收起工作台' }).click()
    await page.getByRole('button', { name: '打开工作台' }).click()
    await expect(skillTab).toHaveClass(/active/)
  },

  C011: async ({ page }) => {
    const { chatStartCalls } = await openTeacherApp(page)

    const homeworkSkillCard = page.locator('.skill-card').filter({ has: page.getByText('作业生成') }).first()
    await homeworkSkillCard.getByRole('button', { name: '插入 $' }).click()
    await page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER).type(' 触发技能')
    await page.getByRole('button', { name: '发送' }).click()

    await expect.poll(() => chatStartCalls.length).toBe(1)
    expect(chatStartCalls[0].skill_id).toBe('homework-generator')
  },

  C012: async ({ page }) => {
    const { chatStartCalls } = await openTeacherApp(page)
    const composer = page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER)

    const homeworkSkillCard = page.locator('.skill-card').filter({ has: page.getByText('作业生成') }).first()

    await homeworkSkillCard.getByRole('button', { name: '插入 $' }).click()
    const base = (await composer.inputValue()).trim()
    await composer.fill(`${base} 混合场景 $teacher-assignment-ops`)
    await page.getByRole('button', { name: '发送' }).click()

    await expect.poll(() => chatStartCalls.length).toBe(1)
    expect(chatStartCalls[0].skill_id).toBe('teacher-assignment-ops')
  },

  D001: async ({ page }) => {
    let uploadCalls = 0
    await openTeacherApp(page, { stateOverrides: { teacherWorkbenchTab: 'workflow' } })

    await page.route('http://localhost:8000/assignment/upload/start', async (route) => {
      uploadCalls += 1
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
    })

    await workflowUploadSubmitButton(page).click()
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
    await workflowUploadSubmitButton(page).click()

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
    await workflowAssignmentScopeSelect(page).selectOption('class')
    await page.locator('#workflow-upload-section input[type="file"]').first().setInputFiles(fakePdfFile)
    await workflowUploadSubmitButton(page).click()

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
    await workflowAssignmentScopeSelect(page).selectOption('student')
    await page.locator('#workflow-upload-section input[type="file"]').first().setInputFiles(fakePdfFile)
    await workflowUploadSubmitButton(page).click()

    await expect(page.getByText('私人作业请填写学生编号')).toBeVisible()
    expect(uploadCalls).toBe(0)
  },

  D005: async ({ page }) => {
    await openTeacherApp(page, { stateOverrides: { teacherWorkbenchTab: 'workflow' } })

    await page.route('http://localhost:8000/assignment/upload/start', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, job_id: 'job_d005', status: 'queued' }),
      })
    })

    await page.getByPlaceholder('例如：HW-2026-02-05').fill('HW-D005')
    await page.locator('#workflow-upload-section input[type="file"]').first().setInputFiles(fakePdfFile)
    await workflowUploadSubmitButton(page).click()

    await expect.poll(async () =>
      page.evaluate(() => {
        const raw = localStorage.getItem('teacherActiveUpload')
        return raw ? JSON.parse(raw) : null
      }),
    ).toEqual({ type: 'assignment', job_id: 'job_d005' })
  },

  D006: async ({ page }) => {
    const jobId = 'job_d006'
    const seenStatuses: string[] = []

    await setupTeacherState(page, {
      stateOverrides: {
        teacherWorkbenchTab: 'workflow',
        teacherActiveUpload: JSON.stringify({ type: 'assignment', job_id: jobId }),
      },
    })
    await setupBasicTeacherApiMocks(page)

    let statusCalls = 0
    await page.route('http://localhost:8000/assignment/upload/status**', async (route) => {
      statusCalls += 1
      const payload =
        statusCalls === 1
          ? { job_id: jobId, status: 'queued', progress: 10 }
          : statusCalls === 2
            ? { job_id: jobId, status: 'processing', progress: 45 }
            : {
                job_id: jobId,
                status: 'done',
                progress: 100,
                assignment_id: 'HW-D006',
                requirements_missing: [],
              }
      seenStatuses.push(String(payload.status))
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(payload),
      })
    })
    await page.route('http://localhost:8000/assignment/upload/draft**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, draft: buildAssignmentDraft(jobId, 'HW-D006') }),
      })
    })

    await page.goto('/')
    await page.getByRole('button', { name: '刷新状态' }).click()
    await page.getByRole('button', { name: '刷新状态' }).click()
    await expect(workflowStatusChip(page)).toContainText('待审核')
    expect(seenStatuses).toContain('queued')
    expect(seenStatuses).toContain('processing')
    expect(seenStatuses).toContain('done')
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
    await expect(workflowStatusChip(page)).toHaveText('解析失败')
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

    const assignmentSection = page.locator('#workflow-assignment-draft-section')
    const requirementsCard = assignmentSection.locator('.draft-card').first()
    await requirementsCard.locator('input').nth(1).fill('电场综合')
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

    const confirmBtn = assignmentConfirmButton(page)
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

    const confirmBtn = assignmentConfirmButton(page)
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

    const confirmBtn = assignmentConfirmButton(page)
    await confirmBtn.click()

    await expect(confirmBtn).toHaveText('已创建')
    await expect.poll(async () => page.evaluate(() => localStorage.getItem('teacherActiveUpload'))).toBeNull()
  },

  D012: async ({ page }) => {
    const jobId = 'job_d012_not_ready'

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
          assignment_id: 'HW-D012',
          requirements_missing: [],
        }),
      })
    })
    await page.route('http://localhost:8000/assignment/upload/draft**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, draft: buildAssignmentDraft(jobId, 'HW-D012') }),
      })
    })
    await page.route('http://localhost:8000/assignment/upload/draft/save', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, message: '草稿已保存。' }) })
    })
    await page.route('http://localhost:8000/assignment/upload/confirm', async (route) => {
      await route.fulfill({
        status: 409,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: {
            error: 'job_not_ready',
            message: '解析尚未完成',
            progress: 78,
          },
        }),
      })
    })

    await page.goto('/')
    await assignmentConfirmButton(page).click()

    await expect(page.locator('#workflow-assignment-draft-section').getByText('解析尚未完成（进度 78%）')).toBeVisible()
    await expect(page.locator('#workflow-assignment-draft-section')).toBeVisible()
    await expect.poll(async () => page.evaluate(() => localStorage.getItem('teacherActiveUpload'))).not.toBeNull()
  },

  D013: async ({ page }) => {
    const jobId = 'job_d013_restore'
    let statusCalls = 0

    await setupTeacherState(page, {
      stateOverrides: {
        teacherWorkbenchTab: 'workflow',
        teacherActiveUpload: JSON.stringify({ type: 'assignment', job_id: jobId }),
      },
    })
    await setupBasicTeacherApiMocks(page)
    await page.route('http://localhost:8000/assignment/upload/status**', async (route) => {
      statusCalls += 1
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          job_id: jobId,
          status: 'done',
          progress: 100,
          assignment_id: 'HW-D013',
          requirements_missing: [],
        }),
      })
    })
    await page.route('http://localhost:8000/assignment/upload/draft**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, draft: buildAssignmentDraft(jobId, 'HW-D013') }),
      })
    })

    await page.goto('/')
    await expect(page.locator('#workflow-assignment-draft-section')).toBeVisible()
    await expect(page.locator('#workflow-assignment-draft-section').getByText('作业编号：HW-D013', { exact: true })).toBeVisible()

    await page.reload()
    await expect(page.locator('#workflow-assignment-draft-section')).toBeVisible()
    await expect.poll(() => statusCalls).toBeGreaterThan(1)
  },

  D014: async ({ page }) => {
    let startBodyText = ''
    await openTeacherApp(page, { stateOverrides: { teacherWorkbenchTab: 'workflow' } })

    await page.route('http://localhost:8000/assignment/upload/start', async (route) => {
      startBodyText = route.request().postData() || ''
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, job_id: 'job_d014', status: 'queued' }),
      })
    })

    await page.getByPlaceholder('例如：HW-2026-02-05').fill('HW-D014')
    await page.locator('#workflow-upload-section input[type="file"]').first().setInputFiles({
      name: 'question.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('question'),
    })
    await page.locator('#workflow-upload-section input[type="file"]').nth(1).setInputFiles({
      name: 'answer.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('answer'),
    })
    await workflowUploadSubmitButton(page).click()

    await expect.poll(() => startBodyText.length).toBeGreaterThan(0)
    expect(startBodyText).toContain('name="files"')
    expect(startBodyText).toContain('filename="question.pdf"')
    expect(startBodyText).toContain('name="answer_files"')
    expect(startBodyText).toContain('filename="answer.pdf"')
  }
}

test('workflow tab keeps must-do upload actions ahead of supplementary timeline', async ({ page }) => {
  await setupTeacherState(page, {
    stateOverrides: {
      teacherWorkbenchTab: 'workflow',
    },
  })
  await setupBasicTeacherApiMocks(page)

  await page.goto('/')

  const timelineHeading = page.getByText('最近一次执行')
  const nextStepHeading = page.getByText('必做动作', { exact: true })
  const uploadSection = workflowUploadSection(page)

  await expect(timelineHeading).toBeVisible()
  await expect(nextStepHeading).toBeVisible()
  await expect(uploadSection).toBeVisible()

  const nextStepBox = await nextStepHeading.boundingBox()
  const timelineBox = await timelineHeading.boundingBox()
  const uploadBox = await uploadSection.boundingBox()

  expect(nextStepBox?.y ?? 0).toBeLessThan(uploadBox?.y ?? 0)
  expect(uploadBox?.y ?? 0).toBeLessThan(timelineBox?.y ?? 0)
})

test('teacher surface keeps a single full next-step instruction across task strip and workflow shells', async ({ page }) => {
  await setupTeacherState(page, {
    stateOverrides: {
      teacherWorkbenchTab: 'workflow',
    },
  })
  await setupBasicTeacherApiMocks(page)

  await page.goto('/')

  await expect(page.getByText(/下一步：/)).toHaveCount(0)
  await expect(page.getByText('今日重心')).toHaveCount(0)
})

registerMatrixCases('Teacher Skill Workbench', skillWorkbenchCases, implementations)
registerMatrixCases('Teacher Assignment Workflow', assignmentWorkflowCases, implementations)
