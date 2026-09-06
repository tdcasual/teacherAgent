import { describe, expect, it } from 'vitest'

import { assignmentIdForStudentSend, isFreeAskSession } from './studentSendAssignment'

describe('assignmentIdForStudentSend', () => {
  it('drops assignment_id for free-ask sessions even when selected', () => {
    expect(isFreeAskSession('general_2026-08-28')).toBe(true)
    expect(
      assignmentIdForStudentSend({
        sessionId: 'general_2026-08-28',
        selectedAssignmentId: 'HW_A',
        sessionAssignmentId: '',
      }),
    ).toBeUndefined()
  })

  it('prefers the active session stored assignment_id over a sticky selection', () => {
    expect(
      assignmentIdForStudentSend({
        sessionId: 's_old',
        selectedAssignmentId: 'HW_A',
        sessionAssignmentId: 'HW_B',
      }),
    ).toBe('HW_B')
  })

  it('uses selected assignment for a new today session not yet in the index', () => {
    expect(
      assignmentIdForStudentSend({
        sessionId: 'HW_A',
        selectedAssignmentId: 'HW_A',
        sessionAssignmentId: '',
      }),
    ).toBe('HW_A')
  })
})
