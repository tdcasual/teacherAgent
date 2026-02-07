import { expect, test, type Page } from '@playwright/test'

type ChatStartPayload = {
  request_id?: string
  session_id?: string
  messages?: Array<{ role?: string; content?: string }>
  role?: string
  agent_id?: string
  skill_id?: string
}

type SetupOptions = {
  historyMessages?: Array<{ ts?: string; role?: string; content?: string }>
}

const mockSkills = [
  {
    id: 'physics-teacher-ops',
    title: '教学运营',
    desc: '老师运营流程',
    prompts: ['请总结班级学习情况'],
    examples: ['查看班级趋势'],
    allowed_roles: ['teacher'],
  },
  {
    id: 'physics-homework-generator',
    title: '作业生成',
    desc: '生成分层作业',
    prompts: ['生成静电场作业'],
    examples: ['高二静电场 8 题'],
    allowed_roles: ['teacher'],
  },
]

const setupTeacherState = async (page: Page) => {
  await page.addInitScript(() => {
    localStorage.clear()
    localStorage.setItem('teacherMainView', 'chat')
    localStorage.setItem('teacherSessionSidebarOpen', 'false')
    localStorage.setItem('teacherSkillsOpen', 'true')
    localStorage.setItem('teacherWorkbenchTab', 'skills')
    localStorage.setItem('teacherSkillPinned', 'false')
    localStorage.setItem('teacherActiveSkillId', 'physics-teacher-ops')
    localStorage.setItem('teacherActiveAgentId', 'default')
    localStorage.setItem('apiBaseTeacher', 'http://localhost:8000')
  })
}

const setupApiMocks = async (page: Page, options: SetupOptions = {}) => {
  const chatStartCalls: ChatStartPayload[] = []
  const statusReplies = new Map<string, string>()

  await page.route('http://localhost:8000/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const method = request.method().toUpperCase()
    const path = url.pathname

    if (method === 'GET' && path === '/skills') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ skills: mockSkills }),
      })
      return
    }

    if (method === 'GET' && path === '/teacher/history/sessions') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, teacher_id: 'T001', sessions: [], next_cursor: null, total: 0 }),
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
          messages: options.historyMessages || [],
          next_cursor: -1,
        }),
      })
      return
    }

    if (method === 'POST' && path === '/chat/start') {
      const payload = JSON.parse(request.postData() || '{}') as ChatStartPayload
      chatStartCalls.push(payload)
      const jobId = `job_${chatStartCalls.length}`
      const lastUser = payload.messages?.[payload.messages.length - 1]?.content || ''
      statusReplies.set(jobId, `回执：${lastUser}`)
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          job_id: jobId,
          status: 'queued',
          lane_id: 'teacher-main',
          lane_queue_position: 0,
          lane_queue_size: 1,
        }),
      })
      return
    }

    if (method === 'GET' && path === '/chat/status') {
      const jobId = url.searchParams.get('job_id') || ''
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          job_id: jobId,
          status: 'done',
          reply: statusReplies.get(jobId) || '已收到。',
        }),
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true }),
    })
  })

  return { chatStartCalls }
}

const openTeacherApp = async (page: Page, options: SetupOptions = {}) => {
  await setupTeacherState(page)
  const mocks = await setupApiMocks(page, options)
  await page.goto('/')
  await expect(page.getByRole('button', { name: '发送' })).toBeVisible()
  await expect(page.getByPlaceholder('输入指令或问题，使用 @ 查看 Agent、$ 查看技能。回车发送，上档键+回车换行')).toBeVisible()
  return mocks
}

const buildHistoryMessages = (count: number) => {
  const messages: Array<{ ts?: string; role?: string; content?: string }> = []
  for (let i = 1; i <= count; i += 1) {
    messages.push({
      ts: new Date(Date.now() - (count - i) * 1000).toISOString(),
      role: i % 2 === 0 ? 'user' : 'assistant',
      content: `历史消息-${i} ` + '内容 '.repeat(20),
    })
  }
  return messages
}

test('uses @agent and $skill tokens and sends cleaned payload', async ({ page }) => {
  const { chatStartCalls } = await openTeacherApp(page)
  const composer = page.getByPlaceholder('输入指令或问题，使用 @ 查看 Agent、$ 查看技能。回车发送，上档键+回车换行')

  await composer.click()
  await composer.fill('@ope')
  await expect(page.locator('.mention-panel')).toBeVisible()
  await page.getByRole('button', { name: /@opencode/ }).first().click()
  await expect(composer).toHaveValue(/@opencode/)

  await composer.type('$physics-homework-generator 生成作业')
  await page.getByRole('button', { name: '发送' }).click()

  await expect.poll(() => chatStartCalls.length).toBe(1)
  const payload = chatStartCalls[0]
  expect(payload.agent_id).toBe('opencode')
  expect(payload.skill_id).toBe('physics-homework-generator')
  expect(payload.messages?.[payload.messages.length - 1]?.content).toBe('生成作业')

  await expect(page.getByText('回执：生成作业')).toBeVisible()
})

test('auto route mode omits skill_id and warns on unknown $skill', async ({ page }) => {
  const { chatStartCalls } = await openTeacherApp(page)
  const composer = page.getByPlaceholder('输入指令或问题，使用 @ 查看 Agent、$ 查看技能。回车发送，上档键+回车换行')

  await expect(page.getByText('技能: 自动路由')).toBeVisible()
  await composer.fill('$ghost-skill 讲解受力分析')
  await page.getByRole('button', { name: '发送' }).click()

  await expect(page.getByText('未识别的技能：$ghost-skill，已使用自动路由')).toBeVisible()
  await expect.poll(() => chatStartCalls.length).toBe(1)
  const payload = chatStartCalls[0] as Record<string, unknown>
  expect(payload.agent_id).toBe('default')
  expect(Object.prototype.hasOwnProperty.call(payload, 'skill_id')).toBe(false)
  expect((payload.messages as any[])?.[(payload.messages as any[])?.length - 1]?.content).toBe('讲解受力分析')
})

test('manual skill pin sends skill_id and auto route toggle clears it', async ({ page }) => {
  const { chatStartCalls } = await openTeacherApp(page)
  const composer = page.getByPlaceholder('输入指令或问题，使用 @ 查看 Agent、$ 查看技能。回车发送，上档键+回车换行')
  const sendBtn = page.getByRole('button', { name: '发送' })

  const homeworkSkillCard = page
    .locator('.skill-card')
    .filter({ has: page.getByText('作业生成') })
    .first()
  await expect(homeworkSkillCard).toBeVisible()
  await homeworkSkillCard.getByRole('button', { name: '设为当前' }).click()

  await expect(page.getByText('技能: $physics-homework-generator')).toBeVisible()
  await composer.fill('固定技能请求')
  await sendBtn.click()
  await expect.poll(() => chatStartCalls.length).toBe(1)
  expect(chatStartCalls[0].skill_id).toBe('physics-homework-generator')

  await page.getByRole('button', { name: '使用自动路由' }).click()
  await expect(page.getByText('技能: 自动路由')).toBeVisible()
  await composer.fill('自动路由请求')
  await sendBtn.click()
  await expect.poll(() => chatStartCalls.length).toBe(2)

  const payload = chatStartCalls[1] as Record<string, unknown>
  expect(Object.prototype.hasOwnProperty.call(payload, 'skill_id')).toBe(false)
})

test('keeps chat scroll position when user is reading history', async ({ page }) => {
  test.setTimeout(90_000)
  await openTeacherApp(page, { historyMessages: buildHistoryMessages(80) })

  await expect(page.getByText('历史消息-80')).toBeVisible()

  const messages = page.locator('.messages')
  await messages.evaluate((el) => {
    el.style.height = '140px'
    el.style.maxHeight = '140px'
    el.style.overflow = 'auto'
  })
  await expect.poll(() => messages.evaluate((el) => el.scrollHeight - el.clientHeight)).toBeGreaterThan(0)
  await messages.evaluate((el) => {
    el.scrollTop = 0
    el.dispatchEvent(new Event('scroll'))
  })

  await expect(page.getByRole('button', { name: '回到底部' })).toBeVisible()
  await page.getByRole('button', { name: '回到底部' }).click()

  await expect.poll(() => messages.evaluate((el) => el.scrollHeight - el.clientHeight)).toBeGreaterThan(0)
  await expect
    .poll(() =>
      messages.evaluate((el) => {
        const max = el.scrollHeight - el.clientHeight
        return max - el.scrollTop
      }),
    )
    .toBeLessThanOrEqual(64)
  const metrics = await messages.evaluate((el) => {
    const max = el.scrollHeight - el.clientHeight
    return {
      max,
      distance: max - el.scrollTop,
    }
  })
  expect(metrics.max).toBeGreaterThan(0)
  expect(metrics.distance).toBeLessThanOrEqual(64)
  await expect(page.getByRole('button', { name: '回到底部' })).toBeHidden()
})
