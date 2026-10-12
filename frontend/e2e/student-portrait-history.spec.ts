import { expect, test } from '@playwright/test'
import { openStudentApp } from './helpers/studentHarness'

test('assignment history portrait shows last 5 outcomes and 最近补练 from practice_id', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openStudentApp(page, {
    stateOverrides: {
      studentMobileShellV2: '1',
    },
    apiMocks: {
      historyAssignments: [
        {
          assignment_id: 'HW_NEW',
          title: '最新做题',
          assignment_kind: 'problem_set',
          submitted: true,
          official_score: 12,
          allow_practice: true,
        },
        {
          assignment_id: 'HW_SCENARIO',
          title: '情景作业',
          assignment_kind: 'scenario',
          submitted: true,
          official_score: null,
          allow_practice: false,
        },
        {
          assignment_id: 'HW_OPEN',
          title: '未交实践',
          assignment_kind: 'practical',
          submitted: false,
          official_score: null,
          allow_practice: false,
        },
        {
          assignment_id: 'HW_4',
          title: '第四次',
          assignment_kind: 'science_history',
          submitted: true,
          official_score: 8,
        },
        {
          assignment_id: 'HW_5',
          title: '第五次',
          assignment_kind: 'problem_set',
          submitted: true,
          official_score: 7,
          allow_practice: true,
        },
        {
          assignment_id: 'HW_6',
          title: '第六次应被截断',
          assignment_kind: 'problem_set',
          submitted: true,
          official_score: 6,
        },
      ],
      studentProfile: {
        student_id: 'S001',
        recent_weak_kp: ['牛顿第二定律'],
        weak_kp: ['hidden-legacy-kp'],
        next_focus: '受力分析',
        practice_history: [
          { assignment_id: 'OLD', practice_id: 'practice_old' },
          { assignment_id: 'NEW', practice_id: 'practice_ab' },
          { assignment_id: 'HW_HOMEWORK', source: 'brief_fallback' },
        ],
      },
    },
  })

  await page.getByRole('button', { name: '作业记录' }).click()
  await expect(page.getByTestId('student-assignment-history-page')).toBeVisible()
  await expect(page.getByTestId('student-portrait-card')).toBeVisible()

  await expect(page.getByTestId('student-portrait-recent-weak-kp')).toContainText('牛顿第二定律')
  await expect(page.getByTestId('student-portrait-next-focus')).toContainText('受力分析')
  await expect(page.getByText('hidden-legacy-kp')).toHaveCount(0)

  const outcomes = page.getByTestId('student-portrait-recent-outcomes')
  await expect(outcomes).toContainText('problem_set · 已提交 · 12')
  await expect(outcomes).toContainText('scenario · 已提交 · 已交未评分')
  await expect(outcomes).toContainText('practical · 未提交 · —')
  await expect(outcomes).toContainText('science_history · 已提交 · 8')
  await expect(outcomes).toContainText('problem_set · 已提交 · 7')
  await expect(outcomes).not.toContainText('已提交 · 6')
  await expect(page.getByText('第六次应被截断')).toBeVisible()

  const practice = page.getByTestId('student-portrait-practice-history')
  await expect(practice).toContainText('NEW')
  await expect(practice).toContainText('practice_ab')
  await expect(practice).not.toContainText('OLD')
  await expect(practice).not.toContainText('practice_old')
  await expect(practice).not.toContainText('HW_HOMEWORK')

  await expect(page.getByTestId('student-practice-start-HW_NEW')).toBeVisible()
  await expect(page.getByTestId('student-practice-start-HW_SCENARIO')).toHaveCount(0)
  await expect(page.getByTestId('student-practice-start-HW_OPEN')).toHaveCount(0)
})
