import { expect, test } from '@playwright/test'
import { openTeacherApp } from './helpers/teacherHarness'

const ASSIGNMENT_ID = 'HW-SCENARIO-PROGRESS'

const progressPayload = {
  ok: true,
  assignment_id: ASSIGNMENT_ID,
  assignment_kind: 'scenario',
  date: '2026-10-12',
  counts: {
    expected: 1,
    discussion_pass: 0,
    submitted: 1,
    completed: 0,
    overdue: 0,
  },
  rubric: {
    source: 'rubric.md',
    items: [{ id: '1', text: '能指出情景约束', max_points: null }],
  },
  students: [
    {
      student_id: 'S001',
      student_name: '测试学生',
      class_name: '高二1班',
      complete: false,
      submission: { attempts: 1 },
      official_score: null,
      result: { attempts: 1, official_score: null, overdue: false, submitted: true },
      process: { status: 'none' },
      practice: { assigned: 0, submitted: 0, open: 0, bank_miss: false },
      portrait: {
        recent_weak_kp: ['受力分析'],
        next_focus: '牛顿定律',
        last_source: 'graded',
        last_assignment_id: ASSIGNMENT_ID,
      },
      rubric_suggestion: {
        status: 'ready',
        suggested_score: null,
        source: 'heuristic_none',
        comment: '无文本摘录，请老师按量规目测给分',
      },
    },
  ],
}

test('teacher progress shows portrait snippet and non-problem_set rubric from mock payload', async ({ page }) => {
  await openTeacherApp(page, {
    stateOverrides: {
      teacherWorkbenchTab: 'workflow',
    },
  })

  await page.route('http://localhost:8000/teacher/assignment/progress**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(progressPayload),
    })
  })

  const progressSection = page.getByTestId('workflow-progress-section')
  await expect(progressSection).toBeVisible()
  await progressSection.getByRole('button', { name: '展开' }).click()
  await expect(progressSection.getByTestId('progress-refresh')).toBeVisible()

  await progressSection.getByPlaceholder('例如：A2403_2026-02-04').fill(ASSIGNMENT_ID)
  await progressSection.getByTestId('progress-refresh').click()

  await expect(progressSection.getByTestId('progress-row-S001')).toBeVisible()
  const portrait = progressSection.getByTestId('progress-portrait-S001')
  await expect(portrait).toBeVisible()
  await expect(portrait).toContainText('薄弱：受力分析')
  await expect(portrait).toContainText('下一步：牛顿定律')
  await expect(portrait).toContainText('最近：graded')

  const rubric = progressSection.getByTestId('progress-assignment-rubric')
  await expect(rubric).toBeVisible()
  await expect(rubric).toContainText('能指出情景约束')
  await expect(progressSection.getByText('请按量规目测后手填覆盖')).toBeVisible()
  await expect(progressSection.getByTestId('progress-adopt-rubric-S001')).toHaveCount(0)
  await expect(progressSection.getByTestId('progress-practice-S001')).toContainText('不适用')
})
