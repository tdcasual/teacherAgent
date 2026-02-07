import { expect, test } from '@playwright/test'
import {
  TEACHER_COMPOSER_PLACEHOLDER,
  openTeacherApp,
  setupBasicTeacherApiMocks,
  setupTeacherState,
} from './helpers/teacherHarness'

test('skills favorites filter keeps insertion target and sends cleaned payload', async ({ page }) => {
  const { chatStartCalls } = await openTeacherApp(page)
  const composer = page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER)

  const homeworkSkillCard = page
    .locator('.skill-card')
    .filter({ has: page.getByText('作业生成') })
    .first()
  await expect(homeworkSkillCard).toBeVisible()

  await homeworkSkillCard.getByRole('button', { name: '收藏技能' }).click()
  await page.getByLabel('只看收藏').check()
  await expect(page.locator('.skill-card')).toHaveCount(1)

  await homeworkSkillCard.getByRole('button', { name: '插入 $' }).click()
  await expect(composer).toHaveValue(/\$physics-homework-generator\s*$/)

  await composer.type(' 生成 3 道巩固题')
  await page.getByRole('button', { name: '发送' }).click()

  await expect.poll(() => chatStartCalls.length).toBe(1)
  expect(chatStartCalls[0].skill_id).toBe('physics-homework-generator')
  expect(chatStartCalls[0].messages?.[chatStartCalls[0].messages!.length - 1]?.content).toBe('生成 3 道巩固题')
})

test('workflow assignment confirm button enters confirming state and prevents duplicate requests', async ({ page }) => {
  const jobId = 'job_assignment_ready_1'
  let confirmCalls = 0

  await setupTeacherState(page, {
    stateOverrides: {
      teacherWorkbenchTab: 'workflow',
      teacherActiveUpload: JSON.stringify({ type: 'assignment', job_id: jobId }),
    },
  })
  await setupBasicTeacherApiMocks(page)

  await page.route(`http://localhost:8000/assignment/upload/status**`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        job_id: jobId,
        status: 'done',
        progress: 100,
        assignment_id: 'HW-READY-001',
        question_count: 1,
        requirements_missing: [],
      }),
    })
  })

  await page.route(`http://localhost:8000/assignment/upload/draft**`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        draft: {
          job_id: jobId,
          assignment_id: 'HW-READY-001',
          date: '2026-02-07',
          scope: 'public',
          delivery_mode: 'pdf',
          question_count: 1,
          requirements: {
            subject: '物理',
            topic: '电场强度',
            grade_level: '高二',
            class_level: '中等',
            core_concepts: ['电场', '受力'],
            typical_problem: '受力分析',
            misconceptions: ['单位混淆', '方向判断错误', '忽略边界条件', '公式代入错误'],
            duration_minutes: 40,
            preferences: ['分层训练'],
            extra_constraints: '无',
          },
          requirements_missing: [],
          questions: [{ id: 1, stem: '题干示例' }],
          draft_saved: true,
        },
      }),
    })
  })

  await page.route(`http://localhost:8000/assignment/upload/draft/save`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, message: '草稿已保存。' }),
    })
  })

  await page.route(`http://localhost:8000/assignment/upload/confirm`, async (route) => {
    confirmCalls += 1
    await new Promise((resolve) => setTimeout(resolve, 260))
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        message: '作业已确认创建。',
        assignment_id: 'HW-READY-001',
        question_count: 1,
      }),
    })
  })

  await page.goto('/')
  const confirmBtn = page.locator('.confirm-btn')

  await expect(confirmBtn).toBeVisible()
  await expect(confirmBtn).toHaveText('创建作业')
  await expect(confirmBtn).toBeEnabled()

  await confirmBtn.click()
  await expect(confirmBtn).toBeDisabled()

  await confirmBtn.evaluate((node) => {
    ;(node as HTMLButtonElement).click()
  })

  await expect.poll(() => confirmCalls).toBe(1)
  await expect(confirmBtn).toHaveText('已创建')
})

test('workflow mode switch keeps assignment and exam draft fields isolated', async ({ page }) => {
  await openTeacherApp(page, {
    stateOverrides: {
      teacherWorkbenchTab: 'workflow',
    },
  })

  const assignmentInput = page.getByPlaceholder('例如：HW-2026-02-05')
  await assignmentInput.fill('HW-SWITCH-001')

  await page.getByRole('button', { name: '考试', exact: true }).first().click()
  const examInput = page.getByPlaceholder('例如：EX2403_PHY')
  await expect(examInput).toBeVisible()
  await examInput.fill('EX-SWITCH-009')

  await page.getByRole('button', { name: '作业', exact: true }).first().click()
  await expect(assignmentInput).toHaveValue('HW-SWITCH-001')

  await page.getByRole('button', { name: '考试', exact: true }).first().click()
  await expect(examInput).toHaveValue('EX-SWITCH-009')
})

test('mobile overlay closes both session sidebar and workbench panels', async ({ page }) => {
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
})

test('workbench template path can toggle back to auto routing and omit skill_id', async ({ page }) => {
  const { chatStartCalls } = await openTeacherApp(page)
  const composer = page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER)

  const homeworkSkillCard = page
    .locator('.skill-card')
    .filter({ has: page.getByText('作业生成') })
    .first()
  await expect(homeworkSkillCard).toBeVisible()

  await homeworkSkillCard.getByRole('button', { name: '使用模板' }).first().click()
  await expect(page.getByText('技能: $physics-homework-generator')).toBeVisible()

  await page.getByRole('button', { name: '使用自动路由' }).click()
  await expect(page.getByText('技能: 自动路由')).toBeVisible()

  await composer.fill('工作台自动路由请求')
  await page.getByRole('button', { name: '发送' }).click()

  await expect.poll(() => chatStartCalls.length).toBe(1)
  const payload = chatStartCalls[0] as Record<string, unknown>
  expect(Object.prototype.hasOwnProperty.call(payload, 'skill_id')).toBe(false)
})
