import { expect, test, type Page } from '@playwright/test'

type ChatStartPayload = {
  request_id?: string
  session_id?: string
  messages?: Array<{ role?: string; content?: string }>
  role?: string
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
    localStorage.setItem('apiBaseTeacher', 'http://localhost:8000')
    localStorage.setItem('teacherAuthAccessToken', 'e2e-teacher-token')
    localStorage.setItem(
      'teacherAuthSubject',
      JSON.stringify({
        teacher_id: 'T001',
        teacher_name: '测试老师',
        email: 'teacher@example.com',
      }),
    )
    localStorage.setItem('teacherRoutingTeacherId', 'T001')
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
  await expect(page.getByPlaceholder('输入指令或问题，使用 $ 查看技能。回车发送，上档键+回车换行')).toBeVisible()
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

const buildRoutingOverview = (channelCount: number) => ({
  ok: true,
  teacher_id: 'T001',
  routing: {
    schema_version: 1,
    enabled: true,
    version: 7,
    updated_at: new Date().toISOString(),
    updated_by: 'e2e',
    channels: Array.from({ length: channelCount }, (_, index) => ({
      id: `channel_${index + 1}`,
      title: `渠道 ${index + 1}`,
      target: {
        provider: 'openai',
        mode: 'openai-chat',
        model: 'gpt-4.1-mini',
      },
      params: { temperature: 0.3, max_tokens: 2048 },
      fallback_channels: [],
      capabilities: { tools: true, json: true },
    })),
    rules: [
      {
        id: 'rule_teacher_chat',
        priority: 10,
        enabled: true,
        match: {
          roles: ['teacher'],
          skills: [],
          kinds: ['chat.agent'],
          needs_tools: true,
          needs_json: false,
        },
        route: { channel_id: 'channel_1' },
      },
    ],
  },
  validation: { errors: [], warnings: [] },
  history: [],
  proposals: [],
  catalog: {
    providers: [
      {
        provider: 'openai',
        source: 'env',
        modes: [{ mode: 'openai-chat', default_model: 'gpt-4.1-mini', model_env: 'OPENAI_MODEL' }],
      },
    ],
    defaults: { provider: 'openai', mode: 'openai-chat' },
    fallback_chain: ['openai'],
  },
  config_path: '/tmp/routing.json',
})

const buildProviderRegistryOverview = () => ({
  ok: true,
  teacher_id: 'T001',
  providers: [],
  shared_catalog: {
    providers: [
      {
        provider: 'openai',
        source: 'env',
        modes: [{ mode: 'openai-chat', default_model: 'gpt-4.1-mini', model_env: 'OPENAI_MODEL' }],
      },
    ],
    defaults: { provider: 'openai', mode: 'openai-chat' },
    fallback_chain: ['openai'],
  },
  catalog: {
    providers: [
      {
        provider: 'openai',
        source: 'env',
        modes: [{ mode: 'openai-chat', default_model: 'gpt-4.1-mini', model_env: 'OPENAI_MODEL' }],
      },
    ],
    defaults: { provider: 'openai', mode: 'openai-chat' },
    fallback_chain: ['openai'],
  },
  config_path: '/tmp/provider-registry.json',
})

test('uses $skill tokens and sends cleaned payload', async ({ page }) => {
  const { chatStartCalls } = await openTeacherApp(page)
  const composer = page.getByPlaceholder('输入指令或问题，使用 $ 查看技能。回车发送，上档键+回车换行')

  await composer.click()
  await composer.fill('$')
  await expect(page.locator('.mention-panel')).toBeVisible()
  await page.getByRole('button', { name: /\$physics-homework-generator/ }).first().click()
  await expect(composer).toHaveValue(/\$physics-homework-generator/)

  await composer.type(' 生成作业')
  await page.getByRole('button', { name: '发送' }).click()

  await expect.poll(() => chatStartCalls.length).toBe(1)
  const payload = chatStartCalls[0]
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
  const composer = page.getByPlaceholder('输入指令或问题，使用 $ 查看技能。回车发送，上档键+回车换行')
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

test('desktop wheel follows native hovered scroll container', async ({ page }) => {
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

  const composer = page.getByPlaceholder('输入指令或问题，使用 $ 查看技能。回车发送，上档键+回车换行')
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
  const messagesBox = await page.locator('.messages').boundingBox()
  if (!skillsBox) throw new Error('skills box missing')
  if (!messagesBox) throw new Error('messages box missing')

  await page.mouse.move(skillsBox.x + skillsBox.width / 2, skillsBox.y + 80)
  for (let i = 0; i < 8; i += 1) {
    await page.mouse.wheel(0, 900)
  }

  const afterSkillWheel = await page.evaluate(() => {
    const messages = document.querySelector('.messages') as HTMLElement | null
    const skills = document.querySelector('.skills-body') as HTMLElement | null
    return {
      winY: window.scrollY,
      bodyY: document.scrollingElement ? document.scrollingElement.scrollTop : -1,
      msgTop: messages?.scrollTop ?? -1,
      skTop: skills?.scrollTop ?? -1,
    }
  })
  expect(afterSkillWheel.winY).toBe(0)
  expect(afterSkillWheel.bodyY).toBe(0)
  expect(afterSkillWheel.skTop).toBeGreaterThan(0)
  expect(afterSkillWheel.msgTop).toBe(0)

  await page.mouse.move(messagesBox.x + messagesBox.width / 2, messagesBox.y + 80)
  for (let i = 0; i < 6; i += 1) {
    await page.mouse.wheel(0, 900)
  }

  const afterMessagesWheel = await page.evaluate(() => {
    const messages = document.querySelector('.messages') as HTMLElement | null
    const skills = document.querySelector('.skills-body') as HTMLElement | null
    return {
      winY: window.scrollY,
      bodyY: document.scrollingElement ? document.scrollingElement.scrollTop : -1,
      msgTop: messages?.scrollTop ?? -1,
      skTop: skills?.scrollTop ?? -1,
    }
  })
  expect(afterMessagesWheel.winY).toBe(0)
  expect(afterMessagesWheel.bodyY).toBe(0)
  expect(afterMessagesWheel.msgTop).toBeGreaterThan(afterSkillWheel.msgTop)
})

test('auto route mode omits skill_id and warns on unknown $skill', async ({ page }) => {
  const { chatStartCalls } = await openTeacherApp(page)
  const composer = page.getByPlaceholder('输入指令或问题，使用 $ 查看技能。回车发送，上档键+回车换行')

  await expect(page.getByText('技能: 自动路由')).toBeVisible()
  await composer.fill('$ghost-skill 讲解受力分析')
  await page.getByRole('button', { name: '发送' }).click()

  await expect(page.getByText('未识别的技能：$ghost-skill，已使用自动路由')).toBeVisible()
  await expect.poll(() => chatStartCalls.length).toBe(1)
  const payload = chatStartCalls[0] as Record<string, unknown>
  expect(Object.prototype.hasOwnProperty.call(payload, 'skill_id')).toBe(false)
  expect((payload.messages as any[])?.[(payload.messages as any[])?.length - 1]?.content).toBe('讲解受力分析')
})

test('manual skill pin sends skill_id and auto route toggle clears it', async ({ page }) => {
  const { chatStartCalls } = await openTeacherApp(page)
  const composer = page.getByPlaceholder('输入指令或问题，使用 $ 查看技能。回车发送，上档键+回车换行')
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

test('chat pane naturally overflows and can scroll without forced sizing', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 })
  await openTeacherApp(page, { historyMessages: buildHistoryMessages(120) })
  await expect(page.getByText('历史消息-120')).toBeVisible()

  const before = await page.evaluate(() => {
    const layout = document.querySelector('.teacher-layout') as HTMLElement | null
    const shell = document.querySelector('.chat-shell') as HTMLElement | null
    const messages = document.querySelector('.messages') as HTMLElement | null
    return {
      layoutClient: layout?.clientHeight ?? 0,
      shellClient: shell?.clientHeight ?? 0,
      messagesClient: messages?.clientHeight ?? 0,
      messagesScroll: messages?.scrollHeight ?? 0,
      messagesTop: messages?.scrollTop ?? 0,
    }
  })

  expect(before.layoutClient).toBeGreaterThan(0)
  expect(before.shellClient).toBeLessThanOrEqual(before.layoutClient + 4)
  expect(before.messagesScroll).toBeGreaterThan(before.messagesClient)

  const after = await page.locator('.messages').evaluate((el) => {
    el.scrollTop = el.scrollHeight
    return {
      top: el.scrollTop,
      max: el.scrollHeight - el.clientHeight,
    }
  })
  expect(after.max).toBeGreaterThan(0)
  expect(after.top).toBeGreaterThan(0)
})

test('mobile keeps routing entry accessible', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openTeacherApp(page)
  await expect(page.getByRole('button', { name: '模型路由', exact: true })).toBeVisible()
})

test('routing page can scroll when channel list is long', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 })
  await setupTeacherState(page)
  await setupApiMocks(page)
  await page.route('http://localhost:8000/teacher/llm-routing**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(buildRoutingOverview(80)),
    })
  })
  await page.route('http://localhost:8000/teacher/provider-registry**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(buildProviderRegistryOverview()),
    })
  })
  await page.goto('/')
  await page.getByRole('button', { name: '模型路由', exact: true }).click()
  await expect(page.locator('.routing-page')).toBeVisible()
  await expect
    .poll(async () => page.locator('.routing-item').count())
    .toBeGreaterThan(20)

  const before = await page.evaluate(() => {
    const shell = document.querySelector('.chat-shell') as HTMLElement | null
    const items = Array.from(document.querySelectorAll('.routing-item')) as HTMLElement[]
    const last = items[items.length - 1]
    const rect = last?.getBoundingClientRect()
    return {
      shellTop: shell?.scrollTop ?? 0,
      lastBottom: rect?.bottom ?? -1,
      viewport: window.innerHeight,
      itemCount: items.length,
    }
  })
  expect(before.itemCount).toBeGreaterThan(20)
  expect(before.lastBottom).toBeGreaterThan(before.viewport)

  const box = await page.locator('.chat-shell').boundingBox()
  if (!box) throw new Error('missing chat-shell box')
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
  for (let i = 0; i < 20; i += 1) {
    await page.mouse.wheel(0, 1000)
  }

  const after = await page.evaluate(() => {
    const shell = document.querySelector('.chat-shell') as HTMLElement | null
    return {
      shellTop: shell?.scrollTop ?? 0,
      pageY: window.scrollY,
    }
  })
  expect(after.shellTop > before.shellTop || after.pageY > 0).toBeTruthy()
})

test('dismissed archive confirmation closes session action menu', async ({ page }) => {
  await openTeacherApp(page)
  await page.getByRole('button', { name: '展开会话' }).click()
  await page.getByRole('button', { name: '新建' }).click()

  const trigger = page.locator('.session-menu-trigger').first()
  await expect(trigger).toBeVisible()
  await trigger.click()
  await expect(page.locator('.session-menu')).toBeVisible()

  await page.getByRole('menuitem', { name: '归档', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '确认归档会话？' })
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: '取消', exact: true }).click()

  await expect(page.locator('.session-menu')).toBeHidden()
})

test('archive dialog escape restores focus to session menu trigger', async ({ page }) => {
  await openTeacherApp(page)
  await page.getByRole('button', { name: '展开会话' }).click()
  await page.getByRole('button', { name: '新建' }).click()

  const trigger = page.locator('.session-menu-trigger').first()
  await trigger.click()
  await page.getByRole('menuitem', { name: '归档', exact: true }).click()

  const dialog = page.getByRole('dialog', { name: '确认归档会话？' })
  await expect(dialog).toBeVisible()
  await page.keyboard.press('Escape')

  await expect(dialog).toBeHidden()
  await expect(trigger).toBeFocused()
})

test('keeps pending user message visible when switching sessions before reply finishes', async ({ page }) => {
  await setupTeacherState(page)

  const historyBySession: Record<string, Array<{ ts?: string; role?: string; content?: string }>> = {
    main: [{ ts: new Date().toISOString(), role: 'assistant', content: '历史欢迎消息' }],
    s2: [{ ts: new Date().toISOString(), role: 'assistant', content: '第二会话初始消息' }],
  }
  let pending: { sessionId: string; userText: string; jobId: string } | null = null
  let statusCount = 0

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
      const sessions = Object.entries(historyBySession).map(([sessionId, messages]) => ({
        session_id: sessionId,
        updated_at: new Date().toISOString(),
        message_count: messages.length,
        preview: messages[messages.length - 1]?.content || '',
      }))
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, teacher_id: 'T001', sessions, next_cursor: null, total: sessions.length }),
      })
      return
    }

    if (method === 'GET' && path === '/teacher/history/session') {
      const sessionId = url.searchParams.get('session_id') || 'main'
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          teacher_id: 'T001',
          session_id: sessionId,
          messages: historyBySession[sessionId] || [],
          next_cursor: -1,
        }),
      })
      return
    }

    if (method === 'POST' && path === '/chat/start') {
      const payload = JSON.parse(request.postData() || '{}') as {
        session_id?: string
        messages?: Array<{ role?: string; content?: string }>
      }
      const userText = payload.messages?.[payload.messages.length - 1]?.content || ''
      pending = { sessionId: payload.session_id || 'main', userText, jobId: 'job_pending_switch' }
      statusCount = 0
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          job_id: pending.jobId,
          status: 'queued',
          lane_id: 'teacher-main',
          lane_queue_position: 0,
          lane_queue_size: 1,
        }),
      })
      return
    }

    if (method === 'GET' && path === '/chat/status') {
      statusCount += 1
      if (!pending) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ job_id: 'job_pending_switch', status: 'failed', error: 'missing pending' }),
        })
        return
      }
      if (statusCount < 30) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ job_id: pending.jobId, status: 'processing' }),
        })
        return
      }
      historyBySession[pending.sessionId] = [
        ...(historyBySession[pending.sessionId] || []),
        { ts: new Date().toISOString(), role: 'user', content: pending.userText },
        { ts: new Date().toISOString(), role: 'assistant', content: `回执：${pending.userText}` },
      ]
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          job_id: pending.jobId,
          status: 'done',
          reply: `回执：${pending.userText}`,
        }),
      })
      pending = null
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true }),
    })
  })

  await page.goto('/')
  await page.getByRole('button', { name: '展开会话' }).click()
  const composer = page.getByPlaceholder('输入指令或问题，使用 $ 查看技能。回车发送，上档键+回车换行')
  const sendBtn = page.getByRole('button', { name: '发送' })

  const userText = '会话切换期间不应丢失'
  await composer.fill(userText)
  await sendBtn.click()
  await expect.poll(() => (pending ? pending.sessionId : '')).not.toBe('')
  await expect(page.getByText(userText)).toBeVisible()

  const otherSession = page.locator('.session-item').filter({ hasText: 's2' }).first()
  await expect(otherSession).toBeVisible()
  await otherSession.locator('.session-select').click()

  const mainSession = page.locator('.session-item').filter({ hasText: 'main' }).first()
  await expect(mainSession).toBeVisible()
  await mainSession.locator('.session-select').click()

  await expect(page.getByText(userText)).toBeVisible()
})

test('restores pending messages when chat/start resolves after session switch', async ({ page }) => {
  await setupTeacherState(page)

  const historyBySession: Record<string, Array<{ ts?: string; role?: string; content?: string }>> = {
    main: [{ ts: new Date().toISOString(), role: 'assistant', content: '历史欢迎消息' }],
    s2: [{ ts: new Date().toISOString(), role: 'assistant', content: '第二会话初始消息' }],
  }
  let pending: { sessionId: string; userText: string; jobId: string } | null = null
  let statusCount = 0
  let chatStartSeen = false
  let chatStartResolved = false

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
      const sessions = Object.entries(historyBySession).map(([sessionId, messages]) => ({
        session_id: sessionId,
        updated_at: new Date().toISOString(),
        message_count: messages.length,
        preview: messages[messages.length - 1]?.content || '',
      }))
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, teacher_id: 'T001', sessions, next_cursor: null, total: sessions.length }),
      })
      return
    }

    if (method === 'GET' && path === '/teacher/history/session') {
      const sessionId = url.searchParams.get('session_id') || 'main'
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          teacher_id: 'T001',
          session_id: sessionId,
          messages: historyBySession[sessionId] || [],
          next_cursor: -1,
        }),
      })
      return
    }

    if (method === 'POST' && path === '/chat/start') {
      const payload = JSON.parse(request.postData() || '{}') as {
        session_id?: string
        messages?: Array<{ role?: string; content?: string }>
      }
      const userText = payload.messages?.[payload.messages.length - 1]?.content || ''
      pending = { sessionId: payload.session_id || 'main', userText, jobId: 'job_pending_delayed_start' }
      statusCount = 0
      chatStartSeen = true
      await page.waitForTimeout(500)
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          job_id: pending.jobId,
          status: 'queued',
          lane_id: 'teacher-main',
          lane_queue_position: 0,
          lane_queue_size: 1,
        }),
      })
      chatStartResolved = true
      return
    }

    if (method === 'GET' && path === '/chat/status') {
      statusCount += 1
      if (!pending) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ job_id: 'job_pending_delayed_start', status: 'failed', error: 'missing pending' }),
        })
        return
      }
      if (statusCount < 100) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ job_id: pending.jobId, status: 'processing' }),
        })
        return
      }
      historyBySession[pending.sessionId] = [
        ...(historyBySession[pending.sessionId] || []),
        { ts: new Date().toISOString(), role: 'user', content: pending.userText },
        { ts: new Date().toISOString(), role: 'assistant', content: `回执：${pending.userText}` },
      ]
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          job_id: pending.jobId,
          status: 'done',
          reply: `回执：${pending.userText}`,
        }),
      })
      pending = null
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true }),
    })
  })

  await page.goto('/')
  await page.getByRole('button', { name: '展开会话' }).click()
  const composer = page.getByPlaceholder('输入指令或问题，使用 $ 查看技能。回车发送，上档键+回车换行')
  const sendBtn = page.getByRole('button', { name: '发送' })

  const userText = '延迟建任务时也不能丢消息'
  await composer.fill(userText)
  await sendBtn.click()
  await expect.poll(() => chatStartSeen).toBe(true)

  const otherSession = page.locator('.session-item').filter({ hasText: 's2' }).first()
  await expect(otherSession).toBeVisible()
  await otherSession.locator('.session-select').click()

  const mainSession = page.locator('.session-item').filter({ hasText: 'main' }).first()
  await expect(mainSession).toBeVisible()
  await mainSession.locator('.session-select').click()
  await expect.poll(() => chatStartResolved).toBe(true)

  await expect(page.getByText(userText)).toBeVisible()
  await expect(page.getByText('正在生成…')).toBeVisible()
})

test('restoring pending job keeps only one pending status bubble', async ({ page }) => {
  await setupTeacherState(page)
  await page.addInitScript(() => {
    localStorage.setItem(
      'teacherPendingChatJob',
      JSON.stringify({
        job_id: 'job_restore_pending',
        request_id: 'req_restore_pending',
        placeholder_id: 'asst_restore_pending_1',
        user_text: '描述 武熙语 学生',
        session_id: 'main',
        created_at: Date.now(),
      }),
    )
  })

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
      await page.waitForTimeout(300)
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

    if (method === 'GET' && path === '/chat/status') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          job_id: 'job_restore_pending',
          status: 'processing',
        }),
      })
      return
    }

    if (path === '/teacher/session/view-state') {
      if (method === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ok: true,
            teacher_id: 'teacher',
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
      if (method === 'PUT') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ok: true,
            teacher_id: 'teacher',
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
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true }),
    })
  })

  const pendingStatusCount = async () =>
    page.evaluate(() => {
      const targets = new Set(['正在生成…', '正在恢复上一条回复…'])
      return Array.from(document.querySelectorAll('.message.assistant .text')).filter((el) =>
        targets.has(String((el as HTMLElement).innerText || '').trim()),
      ).length
    })

  await page.goto('/')
  await expect(page.getByRole('button', { name: '发送' })).toBeVisible()

  let maxPendingStatusCount = 0
  for (let i = 0; i < 16; i += 1) {
    const current = await pendingStatusCount()
    maxPendingStatusCount = Math.max(maxPendingStatusCount, current)
    await page.waitForTimeout(120)
  }
  expect(maxPendingStatusCount).toBeLessThanOrEqual(1)
})

test('keeps draft session in sidebar after page reload before server persists it', async ({ page }) => {
  await page.addInitScript(() => {
    const FLAG = '__teacher_reload_test_bootstrapped__'
    if (sessionStorage.getItem(FLAG) === '1') return
    sessionStorage.setItem(FLAG, '1')
    localStorage.clear()
    localStorage.setItem('teacherMainView', 'chat')
    localStorage.setItem('teacherSessionSidebarOpen', 'true')
    localStorage.setItem('teacherSkillsOpen', 'true')
    localStorage.setItem('teacherWorkbenchTab', 'skills')
    localStorage.setItem('teacherSkillPinned', 'false')
    localStorage.setItem('teacherActiveSkillId', 'physics-teacher-ops')
    localStorage.setItem('apiBaseTeacher', 'http://localhost:8000')
    localStorage.setItem('teacherAuthAccessToken', 'e2e-teacher-token')
    localStorage.setItem(
      'teacherAuthSubject',
      JSON.stringify({
        teacher_id: 'T001',
        teacher_name: '测试老师',
        email: 'teacher@example.com',
      }),
    )
    localStorage.setItem('teacherRoutingTeacherId', 'T001')
  })

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
        body: JSON.stringify({
          ok: true,
          teacher_id: 'T001',
          sessions: [
            { session_id: 'main', updated_at: new Date().toISOString(), message_count: 1, preview: 'main' },
            { session_id: 's2', updated_at: new Date().toISOString(), message_count: 1, preview: 's2' },
          ],
          next_cursor: null,
          total: 2,
        }),
      })
      return
    }

    if (method === 'GET' && path === '/teacher/history/session') {
      const sessionId = url.searchParams.get('session_id') || 'main'
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          teacher_id: 'T001',
          session_id: sessionId,
          messages: [{ ts: new Date().toISOString(), role: 'assistant', content: `history-${sessionId}` }],
          next_cursor: -1,
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

  await page.goto('/')
  await page.getByRole('button', { name: '新建' }).click()

  const draftId = (await page.locator('.session-item .session-id').first().textContent())?.trim() || ''
  expect(draftId.startsWith('session_')).toBe(true)

  await page.reload()
  await expect(page.locator('.session-id', { hasText: draftId })).toBeVisible()
})
