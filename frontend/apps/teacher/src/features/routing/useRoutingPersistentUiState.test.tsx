import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { safeLocalStorageGetItem, safeLocalStorageSetItem } from '../../utils/storage'
import { useRoutingPersistentUiState } from './useRoutingPersistentUiState'

vi.mock('../../utils/storage', () => ({
  safeLocalStorageGetItem: vi.fn(),
  safeLocalStorageSetItem: vi.fn(),
}))

const safeLocalStorageGetItemMock = vi.mocked(safeLocalStorageGetItem)
const safeLocalStorageSetItemMock = vi.mocked(safeLocalStorageSetItem)

describe('useRoutingPersistentUiState', () => {
  beforeEach(() => {
    safeLocalStorageGetItemMock.mockReset()
    safeLocalStorageSetItemMock.mockReset()
  })

  it('initializes from storage-backed defaults', () => {
    safeLocalStorageGetItemMock.mockImplementation((key: string) => {
      if (key === 'teacherRoutingTeacherId') return 'teacher-42'
      if (key === 'teacherRoutingManualReview') return '1'
      if (key === 'teacherRoutingHistoryExpanded') return '1'
      return null
    })

    const { result } = renderHook(() => useRoutingPersistentUiState())

    expect(result.current.teacherId).toBe('teacher-42')
    expect(result.current.showManualReview).toBe(true)
    expect(result.current.showHistoryVersions).toBe(true)
  })

  it('writes updated values back to storage', () => {
    safeLocalStorageGetItemMock.mockReturnValue(null)

    const { result } = renderHook(() => useRoutingPersistentUiState())

    act(() => {
      result.current.setTeacherId('teacher-new')
      result.current.setShowManualReview(true)
      result.current.setShowHistoryVersions(true)
    })

    expect(safeLocalStorageSetItemMock).toHaveBeenCalledWith('teacherRoutingTeacherId', 'teacher-new')
    expect(safeLocalStorageSetItemMock).toHaveBeenCalledWith('teacherRoutingManualReview', '1')
    expect(safeLocalStorageSetItemMock).toHaveBeenCalledWith('teacherRoutingHistoryExpanded', '1')
  })
})
