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

const buildSkills = (count: number) =>
  Array.from({ length: count }, (_, index) => ({
    id: `physics-skill-${index + 1}`,
    title: `技能-${index + 1}`,
    desc: `技能描述-${index + 1}`,
    prompts: ['执行示例'],
    examples: ['示例问题'],
    allowed_roles: ['teacher'],
  }))

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

test('desktop enforces isolated scroll contract', async ({ page }) => {
  const denseSkills = buildSkills(60)
  await setupTeacherState(page)
  await setupApiMocks(page, { historyMessages: buildHistoryMessages(120) })
  await page.route('http://localhost:8000/skills', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ skills: denseSkills }),
    })
  })
  await page.goto('/')
  await page.getByRole('button', { name: '展开会话' }).click()

  const appOverflow = await page.locator('.app.teacher').evaluate((el) => getComputedStyle(el).overflowY)
  const bodyOverflow = await page.evaluate(() => getComputedStyle(document.body).overflowY)
  const messagesOverscroll = await page.locator('.messages').evaluate((el) => getComputedStyle(el).overscrollBehaviorY)
  const sessionOverscroll = await page.locator('.session-groups').evaluate((el) => getComputedStyle(el).overscrollBehaviorY)
  const skillsOverscroll = await page.locator('.skills-body').evaluate((el) => getComputedStyle(el).overscrollBehaviorY)

  expect(appOverflow).toBe('hidden')
  expect(bodyOverflow).toBe('hidden')
  expect(messagesOverscroll).toBe('contain')
  expect(sessionOverscroll).toBe('contain')
  expect(skillsOverscroll).toBe('contain')
})

test('desktop wheel on chat does not move page or side panel anchors', async ({ page }) => {
  const { chatStartCalls } = await openTeacherApp(page)
  await page.getByRole('button', { name: '展开会话' }).click()
  const composer = page.getByPlaceholder('输入指令或问题，使用 @ 查看 Agent、$ 查看技能。回车发送，上档键+回车换行')
  const sendBtn = page.getByRole('button', { name: '发送' })

  for (let i = 1; i <= 28; i += 1) {
    const text = `滚轮锚点回归-${i}`
    await composer.fill(text)
    await sendBtn.click()
    await expect.poll(() => chatStartCalls.length).toBe(i)
    await expect(page.getByText(`回执：${text}`)).toBeVisible()
  }

  await page.locator('.messages').evaluate((el) => {
    el.style.height = '160px'
    el.style.maxHeight = '160px'
    el.style.overflow = 'auto'
    el.scrollTop = el.scrollHeight
    el.dispatchEvent(new Event('scroll'))
  })

  const before = await page.evaluate(() => {
    const left = document.querySelector('.session-sidebar')?.getBoundingClientRect().top ?? -1
    const right = document.querySelector('.skills-panel')?.getBoundingClientRect().top ?? -1
    const messages = document.querySelector('.messages')
    return {
      winY: window.scrollY,
      bodyY: document.scrollingElement ? document.scrollingElement.scrollTop : -1,
      leftTop: left,
      rightTop: right,
      msgTop: messages?.scrollTop ?? -1,
      msgMax: (messages?.scrollHeight ?? 0) - (messages?.clientHeight ?? 0),
    }
  })
  expect(before.msgMax).toBeGreaterThan(0)

  const box = await page.locator('.messages').boundingBox()
  if (!box) throw new Error('messages box missing')
  await page.mouse.move(box.x + box.width / 2, box.y + 120)
  for (let i = 0; i < 14; i += 1) {
    await page.mouse.wheel(0, -900)
  }
  for (let i = 0; i < 20; i += 1) {
    await page.mouse.wheel(0, -900)
  }

  const after = await page.evaluate(() => {
    const left = document.querySelector('.session-sidebar')?.getBoundingClientRect().top ?? -1
    const right = document.querySelector('.skills-panel')?.getBoundingClientRect().top ?? -1
    const messages = document.querySelector('.messages')
    return {
      winY: window.scrollY,
      bodyY: document.scrollingElement ? document.scrollingElement.scrollTop : -1,
      leftTop: left,
      rightTop: right,
      msgTop: messages?.scrollTop ?? -1,
    }
  })

  expect(after.winY).toBe(0)
  expect(after.bodyY).toBe(0)
  expect(after.leftTop).toBeCloseTo(before.leftTop, 1)
  expect(after.rightTop).toBeCloseTo(before.rightTop, 1)
  expect(after.msgTop).toBeLessThan(before.msgTop)
})

test('desktop defaults wheel to chat until side panel is explicitly activated', async ({ page }) => {
  const denseSkills = buildSkills(60)
  await setupTeacherState(page)
  const { chatStartCalls } = await setupApiMocks(page)
  await page.route('http://localhost:8000/skills', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ skills: denseSkills }),
    })
  })
  await page.goto('/')

  const composer = page.getByPlaceholder('输入指令或问题，使用 @ 查看 Agent、$ 查看技能。回车发送，上档键+回车换行')
  const sendBtn = page.getByRole('button', { name: '发送' })

  for (let i = 1; i <= 24; i += 1) {
    const text = `滚轮路由基线-${i}`
    await composer.fill(text)
    await sendBtn.click()
    await expect.poll(() => chatStartCalls.length).toBe(i)
    await expect(page.getByText(`回执：${text}`)).toBeVisible()
  }

  const prepared = await page.evaluate(() => {
    const messages = document.querySelector('.messages') as HTMLElement | null
    const skills = document.querySelector('.skills-body') as HTMLElement | null
    if (!messages || !skills) {
      return { ready: false, msgMax: -1, skMax: -1 }
    }
    messages.style.height = '180px'
    messages.style.maxHeight = '180px'
    messages.style.overflow = 'auto'
    skills.style.height = '220px'
    skills.style.maxHeight = '220px'
    skills.style.overflow = 'auto'
    messages.scrollTop = 0
    skills.scrollTop = 0
    return {
      ready: true,
      msgMax: messages.scrollHeight - messages.clientHeight,
      skMax: skills.scrollHeight - skills.clientHeight,
    }
  })
  expect(prepared.ready).toBe(true)
  expect(prepared.msgMax).toBeGreaterThan(0)
  expect(prepared.skMax).toBeGreaterThan(0)

  const skillsBox = await page.locator('.skills-body').boundingBox()
  if (!skillsBox) throw new Error('skills box missing')

  await page.mouse.move(skillsBox.x + skillsBox.width / 2, skillsBox.y + 80)
  for (let i = 0; i < 8; i += 1) {
    await page.mouse.wheel(0, 900)
  }

  const afterDefaultWheel = await page.evaluate(() => {
    const messages = document.querySelector('.messages') as HTMLElement | null
    const skills = document.querySelector('.skills-body') as HTMLElement | null
    return {
      winY: window.scrollY,
      bodyY: document.scrollingElement ? document.scrollingElement.scrollTop : -1,
      msgTop: messages?.scrollTop ?? -1,
      skTop: skills?.scrollTop ?? -1,
    }
  })
  expect(afterDefaultWheel.winY).toBe(0)
  expect(afterDefaultWheel.bodyY).toBe(0)
  expect(afterDefaultWheel.msgTop).toBeGreaterThan(0)
  expect(afterDefaultWheel.skTop).toBe(0)

  await page.locator('.skills-body').click({ position: { x: 12, y: 12 } })
  for (let i = 0; i < 6; i += 1) {
    await page.mouse.wheel(0, 900)
  }

  const afterSkillActivated = await page.evaluate(() => {
    const messages = document.querySelector('.messages') as HTMLElement | null
    const skills = document.querySelector('.skills-body') as HTMLElement | null
    return {
      msgTop: messages?.scrollTop ?? -1,
      skTop: skills?.scrollTop ?? -1,
    }
  })
  expect(afterSkillActivated.skTop).toBeGreaterThan(afterDefaultWheel.skTop)
  expect(afterSkillActivated.msgTop).toBeCloseTo(afterDefaultWheel.msgTop, 1)

  await page.evaluate(() => {
    const messages = document.querySelector('.messages') as HTMLElement | null
    if (messages) messages.scrollTop = 0
  })
  await page.locator('.messages').click({ position: { x: 20, y: 20 } })
  await page.mouse.move(skillsBox.x + skillsBox.width / 2, skillsBox.y + 80)
  for (let i = 0; i < 6; i += 1) {
    await page.mouse.wheel(0, 900)
  }

  const afterChatReactivated = await page.evaluate(() => {
    const messages = document.querySelector('.messages') as HTMLElement | null
    const skills = document.querySelector('.skills-body') as HTMLElement | null
    return {
      msgTop: messages?.scrollTop ?? -1,
      skTop: skills?.scrollTop ?? -1,
    }
  })
  expect(afterChatReactivated.skTop).toBeCloseTo(afterSkillActivated.skTop, 1)
  expect(afterChatReactivated.msgTop).toBeGreaterThan(0)
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
