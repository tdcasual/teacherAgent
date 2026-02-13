import { safeLocalStorageGetItem, safeLocalStorageRemoveItem, safeLocalStorageSetItem } from '../../../../shared/storage'

export const STUDENT_AUTH_TOKEN_KEY = 'studentAuthAccessToken'

export const readStudentAccessToken = (): string =>
  String(safeLocalStorageGetItem(STUDENT_AUTH_TOKEN_KEY) || '').trim()

export const writeStudentAccessToken = (token: string): void => {
  const text = String(token || '').trim()
  if (!text) {
    safeLocalStorageRemoveItem(STUDENT_AUTH_TOKEN_KEY)
    return
  }
  safeLocalStorageSetItem(STUDENT_AUTH_TOKEN_KEY, text)
}

export const clearStudentAccessToken = (): void => {
  safeLocalStorageRemoveItem(STUDENT_AUTH_TOKEN_KEY)
}
