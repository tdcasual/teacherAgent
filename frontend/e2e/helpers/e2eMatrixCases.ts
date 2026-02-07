import { test } from '@playwright/test'

export type CasePriority = 'P0' | 'P1' | 'P2'

export type MatrixCase = {
  id: string
  priority: CasePriority
  title: string
  given: string
  when: string
  then: string
}

export const registerMatrixCases = (suiteTitle: string, cases: MatrixCase[]) => {
  test.describe(suiteTitle, () => {
    for (const item of cases) {
      test(`${item.id} [${item.priority}] ${item.title}`, async () => {
        test.skip(
          true,
          `TODO | Given: ${item.given} | When: ${item.when} | Then: ${item.then}`,
        )
      })
    }
  })
}
