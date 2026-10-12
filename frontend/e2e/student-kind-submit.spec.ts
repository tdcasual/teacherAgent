import { expect, test, type Page } from '@playwright/test'
import { openStudentApp } from './helpers/studentHarness'

const fakePdfFile = {
  name: 'writeup.pdf',
  mimeType: 'application/pdf',
  buffer: Buffer.from('%PDF-1.4 writeup'),
}

const fakePhotoFile = {
  name: 'lab.png',
  mimeType: 'image/png',
  buffer: Buffer.from([0x89, 0x50, 0x4e, 0x47]),
}

const kindTodayMocks = {
  todayAssignments: [
    {
      assignment_id: 'HW-SCENARIO',
      title: '情景讨论',
      date: '2026-10-12',
      assignment_kind: 'scenario',
      allow_practice: false,
    },
    {
      assignment_id: 'HW-PRACTICAL',
      title: '实验记录',
      date: '2026-10-12',
      assignment_kind: 'practical',
      allow_practice: false,
    },
  ],
}

const todayRow = (page: Page, title: string) =>
  page
    .getByTestId('student-today-assignment-list')
    .locator('div')
    .filter({ has: page.getByRole('heading', { name: title }) })
    .filter({ has: page.getByRole('button', { name: '进入任务' }) })
    .first()

const mockSubmitOk = async (page: Page, assignmentId: string) => {
  await page.route('http://localhost:8000/student/submit', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        submitted: true,
        assignment_id: assignmentId,
        attempt_id: `submission_${assignmentId}`,
        official_score: null,
      }),
    })
  })
}

test('scenario and practical today buttons and chat bar follow kind without 补练', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openStudentApp(page, {
    stateOverrides: {
      studentMobileShellV2: '1',
    },
    apiMocks: kindTodayMocks,
  })

  const list = page.getByTestId('student-today-assignment-list')
  await expect(list).toBeVisible()
  await expect(todayRow(page, '情景讨论').getByRole('button', { name: '提交书面/照片' })).toBeVisible()
  await expect(todayRow(page, '实验记录').getByRole('button', { name: '提交实践照片' })).toBeVisible()
  await expect(list.getByRole('button', { name: '提交作业' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '补练' })).toHaveCount(0)
  await expect(page.getByTestId('student-submit-practice')).toHaveCount(0)
  await expect(page.locator('[data-testid^="student-practice-start-"]')).toHaveCount(0)

  await todayRow(page, '情景讨论').getByRole('button', { name: '进入任务' }).click()
  await expect(page.getByTestId('student-chat-panel')).toBeVisible()
  await expect(
    page.getByTestId('student-chat-panel').getByText('对话不会记为提交', { exact: true }),
  ).toBeVisible()
  await expect(page.getByTestId('student-chat-panel').getByRole('button', { name: '提交书面/照片' })).toBeVisible()
  await expect(page.getByTestId('student-chat-panel').getByRole('button', { name: '提交实践照片' })).toHaveCount(0)
  await expect(page.getByTestId('student-chat-panel').getByRole('button', { name: '提交作业' })).toHaveCount(0)

  await page.getByRole('tab', { name: '学习' }).click()
  await expect(list).toBeVisible()
  await todayRow(page, '实验记录').getByRole('button', { name: '进入任务' }).click()
  await expect(page.getByTestId('student-chat-panel')).toBeVisible()
  await expect(page.getByTestId('student-chat-panel').getByRole('button', { name: '提交实践照片' })).toBeVisible()
  await expect(page.getByTestId('student-chat-panel').getByRole('button', { name: '提交书面/照片' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '补练' })).toHaveCount(0)
})

test('scenario and practical submit copy does not show 补练 card', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openStudentApp(page, {
    stateOverrides: {
      studentMobileShellV2: '1',
    },
    apiMocks: kindTodayMocks,
  })

  await mockSubmitOk(page, 'HW-SCENARIO')
  await todayRow(page, '情景讨论').getByRole('button', { name: '提交书面/照片' }).click()
  await expect(page.getByTestId('student-submit-panel')).toBeVisible()
  await expect(page.getByRole('heading', { name: '提交书面/照片' })).toBeVisible()
  await page.getByTestId('student-submit-file').setInputFiles(fakePdfFile)
  await page.getByRole('button', { name: '提交书面/照片' }).click()
  await expect(page.getByTestId('student-submit-success')).toBeVisible()
  await expect(page.getByTestId('student-submit-result')).toContainText('书面/照片已交')
  await expect(page.getByTestId('student-submit-practice')).toHaveCount(0)
  await expect(page.getByRole('button', { name: '补练' })).toHaveCount(0)
  await expect(page.getByTestId('student-portrait-card')).toHaveCount(0)

  await page.getByRole('button', { name: '返回' }).click()
  await mockSubmitOk(page, 'HW-PRACTICAL')
  await todayRow(page, '实验记录').getByRole('button', { name: '提交实践照片' }).click()
  await expect(page.getByTestId('student-submit-panel')).toBeVisible()
  await expect(page.getByRole('heading', { name: '提交实践照片' })).toBeVisible()
  await page.getByTestId('student-submit-file').setInputFiles(fakePhotoFile)
  await page.getByRole('button', { name: '提交实践照片' }).click()
  await expect(page.getByTestId('student-submit-success')).toBeVisible()
  await expect(page.getByTestId('student-submit-result')).toContainText('实践照片已交')
  await expect(page.getByTestId('student-submit-practice')).toHaveCount(0)
  await expect(page.getByRole('button', { name: '补练' })).toHaveCount(0)
})
