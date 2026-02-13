import { safeLocalStorageGetItem, safeLocalStorageRemoveItem, safeLocalStorageSetItem } from '../../utils/storage'

export const TEACHER_AUTH_ACCESS_TOKEN_KEY = 'teacherAuthAccessToken'
export const TEACHER_AUTH_SUBJECT_KEY = 'teacherAuthSubject'
export const TEACHER_AUTH_EVENT = 'teacher-auth-updated'

export type TeacherAuthSubject = {
  teacher_id: string
  teacher_name: string
  email?: string
}

export const readTeacherAccessToken = (): string =>
  String(safeLocalStorageGetItem(TEACHER_AUTH_ACCESS_TOKEN_KEY) || '').trim()

export const readTeacherAuthSubject = (): TeacherAuthSubject | null => {
  const raw = safeLocalStorageGetItem(TEACHER_AUTH_SUBJECT_KEY)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as Partial<TeacherAuthSubject>
    const teacherId = String(parsed?.teacher_id || '').trim()
    if (!teacherId) return null
    const teacherName = String(parsed?.teacher_name || '').trim() || teacherId
    const email = String(parsed?.email || '').trim()
    return {
      teacher_id: teacherId,
      teacher_name: teacherName,
      ...(email ? { email } : {}),
    }
  } catch {
    return null
  }
}

export const emitTeacherAuthUpdated = (): void => {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new Event(TEACHER_AUTH_EVENT))
}

export const writeTeacherAuthSession = (params: {
  accessToken: string
  teacherId: string
  teacherName: string
  email?: string
}): void => {
  const accessToken = String(params.accessToken || '').trim()
  const teacherId = String(params.teacherId || '').trim()
  if (!accessToken || !teacherId) return
  const teacherName = String(params.teacherName || '').trim() || teacherId
  const email = String(params.email || '').trim()
  safeLocalStorageSetItem(TEACHER_AUTH_ACCESS_TOKEN_KEY, accessToken)
  safeLocalStorageSetItem('teacherRoutingTeacherId', teacherId)
  safeLocalStorageSetItem(
    TEACHER_AUTH_SUBJECT_KEY,
    JSON.stringify({ teacher_id: teacherId, teacher_name: teacherName, ...(email ? { email } : {}) }),
  )
  emitTeacherAuthUpdated()
}

export const clearTeacherAuthSession = (): void => {
  safeLocalStorageRemoveItem(TEACHER_AUTH_ACCESS_TOKEN_KEY)
  safeLocalStorageRemoveItem(TEACHER_AUTH_SUBJECT_KEY)
  safeLocalStorageRemoveItem('teacherRoutingTeacherId')
  emitTeacherAuthUpdated()
}
