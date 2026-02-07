import { expect } from '@playwright/test'
import type { MatrixCase, MatrixCaseRunner } from './helpers/e2eMatrixCases'
import { registerMatrixCases } from './helpers/e2eMatrixCases'
import {
  TEACHER_COMPOSER_PLACEHOLDER,
  openTeacherApp,
  setupBasicTeacherApiMocks,
  setupTeacherState,
} from './helpers/teacherHarness'

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
    core_concepts: ['电场'],
    typical_problem: '综合应用',
    misconceptions: ['方向错误', '单位混乱', '边界遗漏', '公式误用'],
    duration_minutes: 40,
    preferences: ['分层训练'],
    extra_constraints: '无',
  },
  requirements_missing: [],
  questions: [{ id: 1, stem: '题干示例' }],
})

const persistenceRecoveryCases: MatrixCase[] = [
  {
    id: 'G001',
    priority: 'P0',
    title: 'Invalid pinned skill value falls back to auto route',
    given: 'teacherSkillPinned has invalid stored value',
    when: 'Open teacher app',
    then: 'UI falls back to auto-route and payload omits skill_id',
  },
  {
    id: 'G002',
    priority: 'P0',
    title: 'Missing active agent falls back to default',
    given: 'teacherActiveAgentId is missing in local storage',
    when: 'Open teacher app and send chat',
    then: 'Payload uses default agent id',
  },
  {
    id: 'G003',
    priority: 'P1',
    title: 'Unknown workbench tab falls back to default tab',
    given: 'teacherWorkbenchTab is invalid',
    when: 'Open teacher app',
    then: 'Workbench opens with default tab selection',
  },
  {
    id: 'G004',
    priority: 'P0',
    title: 'Pending chat job resumes after refresh',
    given: 'teacherPendingChatJob contains active job metadata',
    when: 'Reload page',
    then: 'Polling resumes and reaches terminal status',
  },
  {
    id: 'G005',
    priority: 'P1',
    title: 'Active upload marker restores workflow context',
    given: 'teacherActiveUpload contains workflow job metadata',
    when: 'Reload page',
    then: 'Workflow mode and polling are restored automatically',
  },
  {
    id: 'G006',
    priority: 'P1',
    title: 'Local and server view-state conflict remains usable',
    given: 'local view-state and server view-state disagree',
    when: 'App performs sync',
    then: 'UI keeps a consistent usable session state',
  },
  {
    id: 'G007',
    priority: 'P1',
    title: 'Corrupt local JSON does not break main flow',
    given: 'Stored JSON for teacher keys is malformed',
    when: 'Open teacher app',
    then: 'App falls back safely and chat remains usable',
  },
  {
    id: 'G008',
    priority: 'P1',
    title: 'Local storage write failure is tolerated',
    given: 'Storage writes throw quota or permission error',
    when: 'Perform chat and workflow actions',
    then: 'Primary flows continue without hard crash',
  },
  {
    id: 'G009',
    priority: 'P1',
    title: 'Custom API base persists across refresh',
    given: 'apiBaseTeacher is customized',
    when: 'Reload and send request',
    then: 'Requests target the configured API base URL',
  },
  {
    id: 'G010',
    priority: 'P0',
    title: 'Refresh during confirm does not duplicate action',
    given: 'Confirm request was triggered and page is refreshed',
    when: 'Wait for terminal status',
    then: 'Final state is consistent and confirm is not duplicated',
  },
]

const mobileA11yCases: MatrixCase[] = [
  {
    id: 'H001',
    priority: 'P0',
    title: 'Mobile overlay closes both side panels',
    given: 'Mobile viewport with session and workbench panels open',
    when: 'Tap overlay',
    then: 'Both panels close',
  },
  {
    id: 'H002',
    priority: 'P1',
    title: 'Session menu aria-expanded reflects open state',
    given: 'Session menu trigger is visible',
    when: 'Open and close session menu',
    then: 'aria-expanded toggles correctly',
  },
  {
    id: 'H003',
    priority: 'P1',
    title: 'Keyboard-only open and close works for session menu',
    given: 'Keyboard focus is on menu trigger',
    when: 'Press Enter then Escape',
    then: 'Menu opens and closes without pointer input',
  },
  {
    id: 'H004',
    priority: 'P1',
    title: 'Mention panel remains keyboard navigable on narrow screens',
    given: 'Mobile width and mention panel opened',
    when: 'Use arrow keys and Enter',
    then: 'Selected token is inserted correctly',
  },
  {
    id: 'H005',
    priority: 'P1',
    title: 'Send button disabled state reflects pending job',
    given: 'A pending chat job exists',
    when: 'Inspect send control',
    then: 'Send button is disabled and status is visible',
  },
  {
    id: 'H006',
    priority: 'P2',
    title: 'High zoom still keeps composer and send reachable',
    given: 'Browser zoom is set near 200 percent',
    when: 'Try typing and sending',
    then: 'Composer and send controls remain visible and clickable',
  },
  {
    id: 'H007',
    priority: 'P2',
    title: 'Landscape mobile keeps critical controls reachable',
    given: 'Mobile landscape viewport',
    when: 'Open teacher app and interact',
    then: 'Core controls remain accessible',
  },
  {
    id: 'H008',
    priority: 'P2',
    title: 'Touch scrolling does not depend on desktop wheel routing',
    given: 'Touch device style scrolling path',
    when: 'Scroll long content with touch gestures',
    then: 'No desktop wheel-only regression appears',
  },
]

const implementations: Partial<Record<string, MatrixCaseRunner>> = {
  G001: async ({ page }) => {
    const { chatStartCalls } = await openTeacherApp(page, {
      stateOverrides: {
        teacherSkillPinned: 'INVALID_BOOL',
      },
    })

    await expect(page.getByText('技能: 自动路由')).toBeVisible()
    await page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER).fill('回退自动路由')
    await page.getByRole('button', { name: '发送' }).click()

    await expect.poll(() => chatStartCalls.length).toBe(1)
    const payload = chatStartCalls[0] as Record<string, unknown>
    expect(Object.prototype.hasOwnProperty.call(payload, 'skill_id')).toBe(false)
  },

  G002: async ({ page }) => {
    const { chatStartCalls } = await openTeacherApp(page, {
      stateOverrides: {
        teacherActiveAgentId: null,
      },
    })

    await page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER).fill('缺省 agent')
    await page.getByRole('button', { name: '发送' }).click()

    await expect.poll(() => chatStartCalls.length).toBe(1)
    expect(chatStartCalls[0].agent_id).toBe('default')
  },

  G004: async ({ page }) => {
    const pending = {
      job_id: 'job_restore_g004',
      request_id: 'req_restore_g004',
      placeholder_id: 'ph_restore_g004',
      user_text: '恢复中的用户消息',
      session_id: 'main',
      created_at: Date.now(),
    }

    await setupTeacherState(page, {
      stateOverrides: {
        teacherPendingChatJob: JSON.stringify(pending),
      },
    })
    await setupBasicTeacherApiMocks(page, {
      onChatStatus: ({ jobId }) => ({
        job_id: jobId,
        status: 'done',
        reply: '恢复完成：最终回复',
      }),
    })

    await page.goto('/')

    await expect(page.locator('.messages').getByText('恢复中的用户消息')).toBeVisible()
    await expect(page.locator('.messages').getByText('恢复完成：最终回复')).toBeVisible()
    await expect.poll(async () => page.evaluate(() => localStorage.getItem('teacherPendingChatJob'))).toBeNull()
  },

  G010: async ({ page }) => {
    const jobId = 'job_confirm_reload_p0'
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
          assignment_id: 'A-RELOAD-P0',
          requirements_missing: [],
        }),
      })
    })

    await page.route('http://localhost:8000/assignment/upload/draft**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, draft: buildAssignmentDraft(jobId, 'A-RELOAD-P0') }),
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
        body: JSON.stringify({
          ok: true,
          message: '作业已确认创建。',
          assignment_id: 'A-RELOAD-P0',
          question_count: 1,
        }),
      })
    })

    await page.goto('/')

    await page.locator('.confirm-btn').click()
    await expect.poll(() => confirmCalls).toBe(1)

    await page.reload()
    await page.waitForTimeout(200)

    expect(confirmCalls).toBe(1)
  },

  H001: async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await openTeacherApp(page, {
      stateOverrides: {
        teacherSessionSidebarOpen: 'true',
        teacherSkillsOpen: 'true',
      },
    })

    await expect(page.getByRole('button', { name: '收起会话' })).toBeVisible()
    await expect(page.getByRole('button', { name: '收起工作台' })).toBeVisible()

    await page.getByLabel('关闭侧边栏').evaluate((node) => {
      ;(node as HTMLButtonElement).click()
    })

    await expect(page.getByRole('button', { name: '展开会话' })).toBeVisible()
    await expect(page.getByRole('button', { name: '打开工作台' })).toBeVisible()
  },
}

registerMatrixCases('Teacher Persistence and Recovery', persistenceRecoveryCases, implementations)
registerMatrixCases('Teacher Mobile and Accessibility', mobileA11yCases, implementations)
