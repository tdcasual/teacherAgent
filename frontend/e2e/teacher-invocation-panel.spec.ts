import { expect, test } from '@playwright/test'
import { TEACHER_COMPOSER_PLACEHOLDER, openTeacherApp } from './helpers/teacherHarness'

test('keyboard mention for skill wraps and inserts selected $skill', async ({ page }) => {
  const { chatStartCalls } = await openTeacherApp(page)
  const composer = page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER)

  await composer.fill('$')
  await expect(page.locator('.mention-panel')).toBeVisible()

  await composer.press('ArrowDown')
  await composer.press('Enter')
  await expect(composer).toHaveValue('$physics-homework-generator ')

  await composer.type('生成 6 题分层练习')
  await page.getByRole('button', { name: '发送' }).click()

  await expect.poll(() => chatStartCalls.length).toBe(1)
  expect(chatStartCalls[0].skill_id).toBe('physics-homework-generator')
  expect(chatStartCalls[0].messages?.[chatStartCalls[0].messages!.length - 1]?.content).toBe('生成 6 题分层练习')
})

test('keyboard mention for skill pins selected skill and sends cleaned prompt', async ({ page }) => {
  const { chatStartCalls } = await openTeacherApp(page)
  const composer = page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER)

  await composer.fill('$')
  await expect(page.locator('.mention-panel')).toBeVisible()

  await composer.press('ArrowDown')
  await composer.press('Enter')
  await expect(composer).toHaveValue('$physics-homework-generator ')
  await expect(page.getByText('技能: $physics-homework-generator')).toBeVisible()

  await composer.type('生成 6 题分层练习')
  await page.getByRole('button', { name: '发送' }).click()

  await expect.poll(() => chatStartCalls.length).toBe(1)
  expect(chatStartCalls[0].skill_id).toBe('physics-homework-generator')
  expect(chatStartCalls[0].messages?.[chatStartCalls[0].messages!.length - 1]?.content).toBe('生成 6 题分层练习')
})

test('unknown $skill shows warning and falls back to auto route', async ({ page }) => {
  const { chatStartCalls } = await openTeacherApp(page)
  const composer = page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER)

  await composer.fill('$ghost-skill 讲解动能定理')
  await page.getByRole('button', { name: '发送' }).click()

  await expect(page.getByText('未识别的技能：$ghost-skill，已使用自动路由')).toBeVisible()
  await expect.poll(() => chatStartCalls.length).toBe(1)
  const payload = chatStartCalls[0] as Record<string, unknown>
  expect(Object.prototype.hasOwnProperty.call(payload, 'skill_id')).toBe(false)
  expect(chatStartCalls[0].messages?.[chatStartCalls[0].messages!.length - 1]?.content).toBe('讲解动能定理')
})

test('invocation-only input is blocked from sending', async ({ page }) => {
  const { chatStartCalls } = await openTeacherApp(page)
  const composer = page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER)

  await composer.fill('$physics-homework-generator')
  await page.getByRole('button', { name: '发送' }).click()

  await page.waitForTimeout(200)
  await expect(composer).toHaveValue('$physics-homework-generator')
  expect(chatStartCalls.length).toBe(0)
})

test('Shift+Enter inserts newline and does not submit immediately', async ({ page }) => {
  const { chatStartCalls } = await openTeacherApp(page)
  const composer = page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER)

  await composer.fill('第一行')
  await composer.press('Shift+Enter')
  await composer.type('第二行')
  await expect(composer).toHaveValue('第一行\n第二行')
  expect(chatStartCalls.length).toBe(0)

  await page.getByRole('button', { name: '发送' }).click()
  await expect.poll(() => chatStartCalls.length).toBe(1)
  expect(chatStartCalls[0].messages?.[chatStartCalls[0].messages!.length - 1]?.content).toBe('第一行\n第二行')
})

test('invalid invocation id warns but still sends raw text payload', async ({ page }) => {
  const { chatStartCalls } = await openTeacherApp(page)
  const composer = page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER)

  await composer.fill('$bad!id 讲解带电粒子偏转')
  await page.getByRole('button', { name: '发送' }).click()

  await expect(page.getByText('无效召唤标识：$bad!id')).toBeVisible()
  await expect.poll(() => chatStartCalls.length).toBe(1)
  const payload = chatStartCalls[0] as Record<string, unknown>
  expect(Object.prototype.hasOwnProperty.call(payload, 'skill_id')).toBe(false)
  expect((payload.messages as Array<{ content?: string }>)[(payload.messages as Array<{ content?: string }>).length - 1]?.content).toBe(
    '$bad!id 讲解带电粒子偏转',
  )
})
