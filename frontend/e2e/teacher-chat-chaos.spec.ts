import { expect, test } from '@playwright/test'
import {
  TEACHER_COMPOSER_PLACEHOLDER,
  openTeacherApp,
  setupBasicTeacherApiMocks,
  setupTeacherState,
} from './helpers/teacherHarness'

test('IME composing Enter does not submit chat until composition ends', async ({ page }) => {
  const { chatStartCalls } = await openTeacherApp(page)
  const composer = page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER)

  await composer.fill('输入法回车保护测试')
  await composer.focus()
  await composer.evaluate((node) => {
    const event = new KeyboardEvent('keydown', {
      key: 'Enter',
      bubbles: true,
      cancelable: true,
      isComposing: true,
    })
    node.dispatchEvent(event)
  })

  await page.waitForTimeout(180)
  expect(chatStartCalls.length).toBe(0)

  await page.keyboard.press('Enter')
  await expect.poll(() => chatStartCalls.length).toBe(1)
})

test('cleans multiple invocation tokens and keeps last valid $skill', async ({ page }) => {
  const { chatStartCalls } = await openTeacherApp(page)
  const composer = page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER)

  await composer.fill('$physics-teacher-ops 先说A $physics-homework-generator 再说B $physics-teacher-ops 最终题目')
  await page.getByRole('button', { name: '发送' }).click()

  await expect.poll(() => chatStartCalls.length).toBe(1)
  const payload = chatStartCalls[0]
  expect(payload.skill_id).toBe('physics-teacher-ops')
  expect(payload.messages?.[payload.messages.length - 1]?.content).toBe('先说A 再说B 最终题目')
})

test('status polling retries after transient failure and eventually renders final reply', async ({ page }) => {
  const mocks = await openTeacherApp(page, {
    apiMocks: {
      statusFailuresBeforeDone: 1,
    },
  })
  const composer = page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER)

  await composer.fill('轮询失败重试')
  await page.getByRole('button', { name: '发送' }).click()

  await expect(page.getByText('回执：轮询失败重试')).toBeVisible()
  await expect.poll(() => mocks.getStatusCallCount('job_1')).toBeGreaterThan(1)
})

test('pending job remains attached to source session when switching away', async ({ page }) => {
  const sourceText = '主会话挂起消息'

  await setupTeacherState(page, {
    stateOverrides: {
      teacherSessionSidebarOpen: 'true',
    },
  })
  await setupBasicTeacherApiMocks(page, {
    historyBySession: {
      main: [{ ts: new Date().toISOString(), role: 'assistant', content: 'main 初始化' }],
      s2: [{ ts: new Date().toISOString(), role: 'assistant', content: 's2 初始化' }],
    },
    onChatStatus: ({ jobId, callCount }) =>
      callCount < 3
        ? { job_id: jobId, status: 'processing' }
        : {
            job_id: jobId,
            status: 'done',
            reply: `回执：${sourceText}`,
          },
  })

  await page.goto('/')
  const composer = page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER)

  await composer.fill(sourceText)
  await page.getByRole('button', { name: '发送' }).click()
  await expect(page.locator('.messages').getByText(sourceText)).toBeVisible()

  const secondSession = page.locator('.session-item').filter({ hasText: 's2' }).first()
  await secondSession.locator('.session-select').click()
  await expect(page.locator('.messages').getByText(sourceText)).toHaveCount(0)

  const mainSession = page.locator('.session-item').filter({ hasText: 'main' }).first()
  await mainSession.locator('.session-select').click()
  await expect(page.locator('.messages').getByText(sourceText)).toBeVisible()
  await expect(page.locator('.messages').getByText(`回执：${sourceText}`)).toBeVisible()

  await secondSession.locator('.session-select').click()
  await expect(page.locator('.messages').getByText(`回执：${sourceText}`)).toHaveCount(0)
})

test('session action menu closes on outside click and Escape key', async ({ page }) => {
  await openTeacherApp(page, {
    stateOverrides: {
      teacherSessionSidebarOpen: 'true',
    },
  })

  const trigger = page.locator('.session-menu-trigger').first()
  await expect(trigger).toBeVisible()

  await trigger.click()
  await expect(page.locator('.session-menu')).toBeVisible()

  await page.locator('.messages').click({ position: { x: 20, y: 20 } })
  await expect(page.locator('.session-menu')).toBeHidden()

  await trigger.click()
  await expect(page.locator('.session-menu')).toBeVisible()

  await page.keyboard.press('Escape')
  await expect(page.locator('.session-menu')).toBeHidden()
})

test('invalid teacherSkillPinned localStorage falls back to auto routing payload', async ({ page }) => {
  const { chatStartCalls } = await openTeacherApp(page, {
    stateOverrides: {
      teacherSkillPinned: 'INVALID_BOOL',
    },
  })

  await expect(page.getByText('技能: 自动路由')).toBeVisible()
  await page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER).fill('污染状态回退')
  await page.getByRole('button', { name: '发送' }).click()

  await expect.poll(() => chatStartCalls.length).toBe(1)
  const payload = chatStartCalls[0] as Record<string, unknown>
  expect(Object.prototype.hasOwnProperty.call(payload, 'skill_id')).toBe(false)
})

test('restores pending chat job from localStorage and completes it', async ({ page }) => {
  const pending = {
    job_id: 'job_restore_1',
    request_id: 'req_restore_1',
    placeholder_id: 'ph_restore_1',
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
})
