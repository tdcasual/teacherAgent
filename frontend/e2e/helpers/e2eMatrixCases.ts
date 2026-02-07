import { test, type APIRequestContext, type Page } from '@playwright/test'

export type CasePriority = 'P0' | 'P1' | 'P2'

export type MatrixCase = {
  id: string
  priority: CasePriority
  title: string
  given: string
  when: string
  then: string
}

export type MatrixCaseRunner = (args: {
  page: Page
  request: APIRequestContext
  browserName: string
}) => Promise<void>

export const registerMatrixCases = (
  suiteTitle: string,
  cases: MatrixCase[],
  implementations: Partial<Record<string, MatrixCaseRunner>> = {},
) => {
  test.describe(suiteTitle, () => {
    for (const item of cases) {
      const implemented = implementations[item.id]
      if (implemented) {
        test(`${item.id} [${item.priority}] ${item.title}`, implemented)
      } else {
        test.skip(
          `${item.id} [${item.priority}] ${item.title}`,
          `TODO | Given: ${item.given} | When: ${item.when} | Then: ${item.then}`,
        )
      }
    }
  })
}
