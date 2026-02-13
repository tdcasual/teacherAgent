import { expect } from '@playwright/test'
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
  workflowStatusChip,
  workflowUploadSubmitButton,
} from './helpers/workflowLocators'

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
    title: 'Missing active skill falls back to default',
    given: 'teacherActiveSkillId is missing in local storage',
    when: 'Open teacher app and send chat',
    then: 'Payload uses default skill fallback behavior',
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
        teacherActiveSkillId: null,
      },
    })

    await page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER).fill('缺省 agent')
    await page.getByRole('button', { name: '发送' }).click()

    await expect.poll(() => chatStartCalls.length).toBe(1)
    expect(Object.prototype.hasOwnProperty.call(chatStartCalls[0] as Record<string, unknown>, 'skill_id')).toBe(false)
  },

  G003: async ({ page }) => {
    await openTeacherApp(page, {
      stateOverrides: {
        teacherWorkbenchTab: 'invalid_tab',
      },
    })

    await expect(page.getByPlaceholder('搜索技能')).toBeVisible()
    await expect.poll(async () => page.evaluate(() => localStorage.getItem('teacherWorkbenchTab'))).toBe('skills')
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
    const { getStatusCallCount } = await setupBasicTeacherApiMocks(page, {
      onChatStatus: ({ jobId }) => ({
        job_id: jobId,
        status: 'done',
        reply: '恢复完成：最终回复',
      }),
    })

    await page.goto('/')

    await expect(page.locator('.messages').getByText('恢复中的用户消息')).toBeVisible()
    await expect.poll(() => getStatusCallCount('job_restore_g004')).toBeGreaterThan(0)
    await expect
      .poll(async () => page.locator('.messages').innerText(), { timeout: 15_000 })
      .toContain('恢复完成：最终回复')
    await expect.poll(async () => page.evaluate(() => localStorage.getItem('teacherPendingChatJob')), { timeout: 15_000 }).toBeNull()
  },

  G005: async ({ page }) => {
    const jobId = 'job_restore_upload_g005'
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
          status: 'processing',
          progress: 35,
          assignment_id: 'A-G005',
        }),
      })
    })

    await page.goto('/')
    await expect(workflowStatusChip(page)).toContainText('解析中')
    await expect.poll(() => statusCalls).toBeGreaterThan(0)

    await page.reload()
    await expect.poll(() => statusCalls).toBeGreaterThan(1)
    await expect(page.getByRole('button', { name: '工作流' })).toHaveClass(/active/)
  },

  G006: async ({ page }) => {
    await setupTeacherState(page, {
      stateOverrides: {
        teacherSessionSidebarOpen: 'true',
        teacherSessionViewState: JSON.stringify({
          title_map: { main: '本地-main' },
          hidden_ids: ['s2'],
          active_session_id: 'main',
          updated_at: '2026-02-07T00:00:00.000Z',
        }),
      },
    })
    await setupBasicTeacherApiMocks(page, {
      historyBySession: {
        main: [{ ts: new Date().toISOString(), role: 'assistant', content: 'main 初始化' }],
        s2: [{ ts: new Date().toISOString(), role: 'assistant', content: 's2 初始化' }],
      },
    })

    await page.route('http://localhost:8000/teacher/session/view-state', async (route) => {
      const method = route.request().method().toUpperCase()
      if (method === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ok: true,
            state: {
              title_map: { s2: '远端-s2' },
              hidden_ids: [],
              active_session_id: 's2',
              updated_at: '2026-02-08T00:00:00.000Z',
            },
          }),
        })
        return
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          state: {
            title_map: { s2: '远端-s2' },
            hidden_ids: [],
            active_session_id: 's2',
            updated_at: new Date().toISOString(),
          },
        }),
      })
    })

    await page.goto('/')
    await expect(page.locator('.session-item').filter({ hasText: '远端-s2' }).first()).toBeVisible()
    await page.locator('.session-item').filter({ hasText: '远端-s2' }).first().locator('.session-select').click()
    await expect(page.locator('.messages').getByText('s2 初始化')).toBeVisible()
  },

  G007: async ({ page }) => {
    const { chatStartCalls } = await openTeacherApp(page, {
      stateOverrides: {
        teacherSkillFavorites: '{bad-json',
        teacherSessionTitles: '{bad-json',
        teacherDeletedSessions: 'not-an-array',
        teacherSessionViewState: 'bad-json',
      },
    })

    await page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER).fill('坏本地数据容错')
    await page.getByRole('button', { name: '发送' }).click()

    await expect.poll(() => chatStartCalls.length).toBe(1)
    await expect(page.locator('.messages').getByText('回执：坏本地数据容错')).toBeVisible()
  },

  G008: async ({ page }) => {
    let startCalls = 0

    await page.addInitScript(() => {
      const rawSetItem = Storage.prototype.setItem
      Storage.prototype.setItem = function patchedSetItem(key: string, value: string) {
        if (key === 'teacherActiveUpload') {
          throw new Error('QuotaExceededError')
        }
        return rawSetItem.call(this, key, value)
      }
    })

    await setupTeacherState(page, {
      stateOverrides: {
        teacherWorkbenchTab: 'workflow',
      },
    })
    await setupBasicTeacherApiMocks(page)

    await page.route('http://localhost:8000/assignment/upload/start', async (route) => {
      startCalls += 1
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, job_id: 'job_g008', status: 'queued' }),
      })
    })

    await page.goto('/')
    await page.getByPlaceholder('例如：HW-2026-02-05').fill('HW-G008')
    await page.locator('#workflow-upload-section input[type="file"]').first().setInputFiles({
      name: 'g008.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('g008'),
    })
    await workflowUploadSubmitButton(page).click()

    await expect.poll(() => startCalls).toBe(1)
    await expect(page.getByRole('heading', { name: '工作台' })).toBeVisible()
  },

  G009: async ({ page }) => {
    const customBase = 'http://127.0.0.1:9001'
    const startRequestUrls: string[] = []

    await setupTeacherState(page, {
      stateOverrides: {
        apiBaseTeacher: customBase,
      },
    })

    await page.route('http://127.0.0.1:9001/**', async (route) => {
      const request = route.request()
      const url = new URL(request.url())
      const method = request.method().toUpperCase()
      const path = url.pathname

      if (method === 'GET' && path === '/skills') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            skills: [
              {
                id: 'physics-teacher-ops',
                title: '教学运营',
                desc: '老师运营流程',
                prompts: ['请总结班级学习情况'],
                examples: ['查看班级趋势'],
                allowed_roles: ['teacher'],
              },
            ],
          }),
        })
        return
      }

      if (method === 'GET' && path === '/teacher/history/sessions') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ok: true,
            teacher_id: 'T001',
            sessions: [{ session_id: 'main', updated_at: new Date().toISOString(), message_count: 0, preview: '' }],
            next_cursor: null,
            total: 1,
          }),
        })
        return
      }

      if (method === 'GET' && path === '/teacher/history/session') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ok: true,
            teacher_id: 'T001',
            session_id: 'main',
            messages: [],
            next_cursor: -1,
          }),
        })
        return
      }

      if (path === '/teacher/session/view-state') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ok: true,
            state: {
              title_map: {},
              hidden_ids: [],
              active_session_id: 'main',
              updated_at: new Date().toISOString(),
            },
          }),
        })
        return
      }

      if (method === 'POST' && path === '/chat/start') {
        startRequestUrls.push(request.url())
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ ok: true, job_id: 'job_g009', status: 'queued', lane_queue_position: 0, lane_queue_size: 1 }),
        })
        return
      }

      if (method === 'GET' && path === '/chat/status') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ job_id: 'job_g009', status: 'done', reply: '回执：自定义 API base' }),
        })
        return
      }

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true }),
      })
    })

    await page.goto('/')
    await page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER).fill('自定义 API base')
    await page.getByRole('button', { name: '发送' }).click()
    await expect(page.locator('.messages').getByText('回执：自定义 API base')).toBeVisible()

    await page.reload()
    await page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER).fill('再次发送')
    await page.getByRole('button', { name: '发送' }).click()
    await expect.poll(() => startRequestUrls.length).toBe(2)
    expect(startRequestUrls.every((url) => url.startsWith(customBase))).toBe(true)
    await expect.poll(async () => page.evaluate(() => localStorage.getItem('apiBaseTeacher'))).toBe(customBase)
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

    await assignmentConfirmButton(page).click()
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

  H002: async ({ page }) => {
    await openTeacherApp(page, {
      stateOverrides: {
        teacherSessionSidebarOpen: 'true',
      },
    })

    const trigger = page.locator('.session-menu-trigger').first()
    await expect(trigger).toHaveAttribute('aria-expanded', 'false')

    await trigger.click()
    await expect(trigger).toHaveAttribute('aria-expanded', 'true')

    await page.locator('.messages').click()
    await expect(trigger).toHaveAttribute('aria-expanded', 'false')
  },

  H003: async ({ page }) => {
    await openTeacherApp(page, {
      stateOverrides: {
        teacherSessionSidebarOpen: 'true',
      },
    })

    const trigger = page.locator('.session-menu-trigger').first()
    await trigger.focus()
    await trigger.press('Enter')
    await expect(page.locator('.session-menu').first()).toBeVisible()
    await expect(trigger).toHaveAttribute('aria-expanded', 'true')

    await trigger.press('Escape')
    await expect(page.locator('.session-menu')).toHaveCount(0)
    await expect(trigger).toHaveAttribute('aria-expanded', 'false')
  },

  H004: async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    const { chatStartCalls } = await openTeacherApp(page)

    const composer = page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER)
    await composer.fill('$')
    await composer.press('ArrowDown')
    await composer.press('Enter')

    await expect(composer).toHaveValue(/\$physics-homework-generator/)
    await composer.type(' 诊断')
    await composer.press('Enter')

    await expect.poll(() => chatStartCalls.length).toBe(1)
    expect(chatStartCalls[0].skill_id).toBe('physics-homework-generator')
  },

  H005: async ({ page }) => {
    await openTeacherApp(page, {
      apiMocks: {
        onChatStatus: ({ jobId }) => ({ job_id: jobId, status: 'processing' }),
      },
    })

    await page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER).fill('pending 状态按钮禁用')
    await page.getByRole('button', { name: '发送' }).click()

    await expect(page.getByRole('button', { name: '发送' })).toBeDisabled()
    await expect(page.locator('.composer-hint')).toContainText('处理中')
    await expect
      .poll(async () => page.evaluate(() => Boolean(localStorage.getItem('teacherPendingChatJob'))))
      .toBe(true)
  },

  H006: async ({ page }) => {
    const { chatStartCalls } = await openTeacherApp(page)

    await page.evaluate(() => {
      document.documentElement.style.zoom = '2'
    })

    const composer = page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER)
    const sendBtn = page.getByRole('button', { name: '发送' })
    await composer.scrollIntoViewIfNeeded()
    await sendBtn.scrollIntoViewIfNeeded()
    await expect(composer).toBeVisible()
    await expect(sendBtn).toBeVisible()

    await composer.fill('高缩放下仍可发送')
    await sendBtn.click()
    await expect.poll(() => chatStartCalls.length).toBe(1)
  },

  H007: async ({ page }) => {
    await page.setViewportSize({ width: 844, height: 390 })
    const { chatStartCalls } = await openTeacherApp(page, {
      stateOverrides: {
        teacherSkillsOpen: 'false',
        teacherSessionSidebarOpen: 'false',
      },
    })

    await expect(page.getByRole('button', { name: '展开会话' })).toBeVisible()
    await expect(page.getByRole('button', { name: '打开工作台' })).toBeVisible()
    await page.getByRole('button', { name: '打开工作台' }).click()
    await expect(page.getByRole('button', { name: '收起工作台' })).toBeVisible()
    await page.getByRole('button', { name: '收起工作台' }).click()
    await expect(page.getByRole('button', { name: '打开工作台' })).toBeVisible()

    const composer = page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER)
    await composer.fill('横屏交互可达')
    await composer.press('Enter')
    await expect.poll(() => chatStartCalls.length).toBe(1)
  },

  H008: async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    const historyBySession = {
      main: Array.from({ length: 140 }).map((_, idx) => ({
        ts: new Date(Date.now() - (140 - idx) * 1000).toISOString(),
        role: idx % 2 === 0 ? 'assistant' : 'user',
        content: `touch-scroll-${idx + 1} ` + '内容 '.repeat(10),
      })),
    }
    const { chatStartCalls } = await openTeacherApp(page, {
      stateOverrides: {
        teacherSkillsOpen: 'false',
      },
      apiMocks: { historyBySession },
    })

    const messages = page.locator('.messages')
    const before = await messages.evaluate((el) => {
      const node = el as HTMLElement
      return {
        top: node.scrollTop,
        max: Math.max(0, node.scrollHeight - node.clientHeight),
      }
    })
    expect(before.max).toBeGreaterThan(0)

    await page.dispatchEvent('.messages', 'pointerdown', {
      pointerType: 'touch',
      isPrimary: true,
      clientX: 180,
      clientY: 520,
      button: 0,
    })
    const after = await messages.evaluate((el) => {
      const node = el as HTMLElement
      const start = node.scrollTop
      node.scrollTop = Math.max(0, start - 260)
      return { start, end: node.scrollTop }
    })
    expect(after.end).toBeLessThan(after.start)

    const composer = page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER)
    await composer.fill('触摸滚动后继续发送')
    await composer.press('Enter')
    await expect.poll(() => chatStartCalls.length).toBe(1)
  },
}

registerMatrixCases('Teacher Persistence and Recovery', persistenceRecoveryCases, implementations)
registerMatrixCases('Teacher Mobile and Accessibility', mobileA11yCases, implementations)
