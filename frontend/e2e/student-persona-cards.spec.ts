import { expect, test } from '@playwright/test'
import { setupStudentState } from './helpers/studentHarness'

type PersonaState = {
  assigned: Array<Record<string, unknown>>
  custom: Array<Record<string, unknown>>
  activePersonaId: string
}

const seedPersonaState = (): PersonaState => ({
  assigned: [
    {
      persona_id: 'preset_1',
      teacher_id: 'T001',
      name: '黛玉风格',
      summary: '细腻、克制、先共情后追问',
      source: 'teacher_assigned',
      review_status: 'approved',
      style_rules: ['先肯定后追问'],
      few_shot_examples: ['你这一步很接近，我们再看一个关键量。'],
    },
  ],
  custom: [
    {
      persona_id: 'custom_1',
      name: '温和教练',
      summary: '耐心拆解每一步',
      source: 'student_custom',
      review_status: 'approved',
      style_rules: ['每次只推进一小步'],
      few_shot_examples: ['我们先确定已知条件，再选公式。'],
      avatar_url: '',
    },
  ],
  activePersonaId: '',
})

const setupPersonaMockRoutes = async (page: Parameters<typeof test>[0]['page'], state: PersonaState) => {
  let viewStatePayload = {
    title_map: {},
    hidden_ids: [],
    active_session_id: 'main',
    updated_at: new Date().toISOString(),
  }

  await page.route('http://localhost:8000/**', async (route) => {
    const request = route.request()
    const method = request.method().toUpperCase()
    const url = new URL(request.url())
    const pathname = url.pathname

    if (method === 'GET' && pathname === '/assignment/today') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, assignment: null }),
      })
      return
    }

    if (method === 'GET' && pathname === '/student/history/sessions') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          student_id: 'S001',
          sessions: [{ session_id: 'main', updated_at: new Date().toISOString(), preview: '欢迎', message_count: 1 }],
          next_cursor: null,
          total: 1,
        }),
      })
      return
    }

    if (method === 'GET' && pathname === '/student/history/session') {
      const sessionId = url.searchParams.get('session_id') || 'main'
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          student_id: 'S001',
          session_id: sessionId,
          messages: [{ ts: new Date().toISOString(), role: 'assistant', content: '欢迎使用学生端' }],
          next_cursor: -1,
        }),
      })
      return
    }

    if (pathname === '/student/session/view-state' && method === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, state: viewStatePayload }),
      })
      return
    }

    if (pathname === '/student/session/view-state' && (method === 'POST' || method === 'PUT')) {
      const body = JSON.parse(request.postData() || '{}') as { state?: Record<string, unknown> }
      const next = body?.state && typeof body.state === 'object' ? body.state : {}
      viewStatePayload = {
        title_map: (next.title_map as Record<string, string>) || {},
        hidden_ids: Array.isArray(next.hidden_ids) ? (next.hidden_ids as string[]) : [],
        active_session_id: String(next.active_session_id || 'main'),
        updated_at: new Date().toISOString(),
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, state: viewStatePayload }),
      })
      return
    }

    if (method === 'GET' && pathname === '/student/personas') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          student_id: 'S001',
          assigned: state.assigned,
          custom: state.custom,
          active_persona_id: state.activePersonaId,
        }),
      })
      return
    }

    if (method === 'POST' && pathname === '/student/personas/activate') {
      const body = JSON.parse(request.postData() || '{}') as { persona_id?: string }
      state.activePersonaId = String(body.persona_id || '')
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          student_id: 'S001',
          active_persona_id: state.activePersonaId,
        }),
      })
      return
    }

    if (method === 'POST' && pathname === '/chat/start') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          job_id: 'student_job_1',
          status: 'done',
          reply: '已收到',
        }),
      })
      return
    }

    if (method === 'GET' && pathname === '/chat/status') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ job_id: 'student_job_1', status: 'done', reply: '已收到' }),
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true }),
    })
  })
}

test('persona toggle defaults to off and selecting card auto-closes picker', async ({ page }) => {
  const state = seedPersonaState()
  let activateCalls = 0
  let activatedPersonaId = ''

  await page.setViewportSize({ width: 1280, height: 900 })
  await setupStudentState(page, { stateOverrides: { studentSidebarOpen: 'false' } })
  await setupPersonaMockRoutes(page, state)
  await page.route('http://localhost:8000/student/personas/activate', async (route) => {
    activateCalls += 1
    const body = JSON.parse(route.request().postData() || '{}') as { persona_id?: string }
    activatedPersonaId = String(body.persona_id || '')
    state.activePersonaId = activatedPersonaId
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, student_id: 'S001', active_persona_id: activatedPersonaId }),
    })
  })

  await page.goto('/')
  await expect(page.getByRole('button', { name: /角色卡：关/ })).toBeVisible()
  await expect(page.getByText('自定义角色', { exact: true })).toHaveCount(0)

  await page.getByRole('button', { name: /角色卡：关/ }).click()
  await expect(page.getByRole('button', { name: /角色卡：开/ })).toBeVisible()
  await expect(page.getByText('自定义角色', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: /黛玉风格/ }).click()
  await expect.poll(() => activateCalls).toBe(1)
  expect(activatedPersonaId).toBe('preset_1')
  await expect(page.getByText('自定义角色', { exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '已选：黛玉风格' })).toBeVisible()
})

test('student custom persona create update and avatar upload form flow works', async ({ page }) => {
  const state = seedPersonaState()
  let createPayload: Record<string, unknown> | null = null
  let updatePayload: Record<string, unknown> | null = null
  let avatarUploadCalls = 0
  let avatarUploadIsMultipart = false
  let updatedPersonaId = ''

  await page.setViewportSize({ width: 1280, height: 900 })
  await setupStudentState(page, { stateOverrides: { studentSidebarOpen: 'false' } })
  await setupPersonaMockRoutes(page, state)

  await page.route('http://localhost:8000/student/personas/custom', async (route) => {
    if (route.request().method().toUpperCase() !== 'POST') {
      await route.fallback()
      return
    }
    createPayload = JSON.parse(route.request().postData() || '{}') as Record<string, unknown>
    const personaId = 'custom_2'
    state.custom.push({
      persona_id: personaId,
      name: String(createPayload?.name || ''),
      summary: String(createPayload?.summary || ''),
      review_status: 'approved',
      style_rules: Array.isArray(createPayload?.style_rules) ? createPayload?.style_rules : [],
      few_shot_examples: Array.isArray(createPayload?.few_shot_examples) ? createPayload?.few_shot_examples : [],
      avatar_url: '',
    })
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, student_id: 'S001', persona: { persona_id: personaId } }),
    })
  })

  await page.route('http://localhost:8000/student/personas/custom/*', async (route) => {
    if (route.request().method().toUpperCase() !== 'PATCH') {
      await route.fallback()
      return
    }
    updatePayload = JSON.parse(route.request().postData() || '{}') as Record<string, unknown>
    const url = new URL(route.request().url())
    const personaId = decodeURIComponent(url.pathname.split('/').pop() || '')
    updatedPersonaId = personaId
    state.custom = state.custom.map((item) => {
      if (String(item.persona_id || '') !== personaId) return item
      return {
        ...item,
        name: String(updatePayload?.name || ''),
        summary: String(updatePayload?.summary || ''),
        style_rules: Array.isArray(updatePayload?.style_rules) ? updatePayload?.style_rules : [],
        few_shot_examples: Array.isArray(updatePayload?.few_shot_examples) ? updatePayload?.few_shot_examples : [],
      }
    })
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, student_id: 'S001', persona: { persona_id: personaId } }),
    })
  })

  await page.route('http://localhost:8000/student/personas/avatar/upload', async (route) => {
    avatarUploadCalls += 1
    const req = route.request()
    const contentType = (await req.headerValue('content-type')) || ''
    avatarUploadIsMultipart = contentType.includes('multipart/form-data')
    const payloadText = req.postDataBuffer()?.toString('utf8') || ''
    const target = state.custom.find((item) => payloadText.includes(String(item.persona_id || '')))
    const personaId = String(target?.persona_id || 'custom_2')
    state.custom = state.custom.map((item) => {
      if (String(item.persona_id || '') !== personaId) return item
      return {
        ...item,
        avatar_url: `/student/personas/avatar/S001/${personaId}/avatar_mock.png`,
      }
    })
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        student_id: 'S001',
        persona_id: personaId,
        avatar_url: `/student/personas/avatar/S001/${personaId}/avatar_mock.png`,
      }),
    })
  })

  await page.goto('/')
  await page.getByRole('button', { name: /角色卡：关/ }).click()
  await expect(page.getByText('自定义角色', { exact: true })).toBeVisible()

  await page.getByPlaceholder('角色名称').fill('曲儿')
  await page.getByPlaceholder('角色摘要').fill('轻快鼓励、循序引导')
  await page.getByPlaceholder('风格规则（每行一条）').fill('先肯定\n再引导')
  await page.getByPlaceholder('示例（每行一条）').fill('你这一步做得很好\n我们再看下一步')
  await page.getByRole('button', { name: '创建自定义角色' }).click()

  await expect(page.getByText('创建成功')).toBeVisible()
  expect(createPayload).toMatchObject({
    student_id: 'S001',
    name: '曲儿',
    summary: '轻快鼓励、循序引导',
  })

  await page.locator('select').selectOption({ label: '曲儿' })
  await page.getByPlaceholder('角色名称').fill('曲儿老师')
  await page.getByPlaceholder('角色摘要').fill('轻快但克制，强调步骤感')
  await page.getByPlaceholder('风格规则（每行一条）').fill('先肯定\n每次只推进一步')
  await page.getByPlaceholder('示例（每行一条）').fill('你做得很好\n下一步我们一起验算')
  await page.getByRole('button', { name: '更新自定义角色' }).click()

  await expect(page.getByText('更新成功')).toBeVisible()
  expect(updatedPersonaId).toBe('custom_2')
  expect(updatePayload).toMatchObject({
    student_id: 'S001',
    name: '曲儿老师',
    summary: '轻快但克制，强调步骤感',
  })

  await page.locator('input[type="file"][accept*=".webp"]').setInputFiles({
    name: 'avatar.png',
    mimeType: 'image/png',
    buffer: Buffer.from('fake-avatar-bytes'),
  })
  await expect.poll(() => avatarUploadCalls).toBe(1)
  expect(avatarUploadIsMultipart).toBe(true)
  await expect(page.getByText('头像上传成功')).toBeVisible()
  await expect(page.getByRole('img', { name: '曲儿老师' }).first()).toHaveAttribute(
    'src',
    /\/student\/personas\/avatar\/S001\/custom_2\/avatar_mock\.png/,
  )
})
