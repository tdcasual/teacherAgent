import { useEffect, useState } from 'react'
import { safeLocalStorageGetItem, safeLocalStorageSetItem } from '../../utils/storage'

export function useRoutingPersistentUiState() {
  const [teacherId, setTeacherId] = useState(() => safeLocalStorageGetItem('teacherRoutingTeacherId') || '')
  const [showManualReview, setShowManualReview] = useState(() => safeLocalStorageGetItem('teacherRoutingManualReview') === '1')
  const [showHistoryVersions, setShowHistoryVersions] = useState(() => safeLocalStorageGetItem('teacherRoutingHistoryExpanded') === '1')

  useEffect(() => {
    safeLocalStorageSetItem('teacherRoutingTeacherId', teacherId)
  }, [teacherId])

  useEffect(() => {
    safeLocalStorageSetItem('teacherRoutingManualReview', showManualReview ? '1' : '0')
  }, [showManualReview])

  useEffect(() => {
    safeLocalStorageSetItem('teacherRoutingHistoryExpanded', showHistoryVersions ? '1' : '0')
  }, [showHistoryVersions])

  return {
    teacherId,
    setTeacherId,
    showManualReview,
    setShowManualReview,
    showHistoryVersions,
    setShowHistoryVersions,
  }
}
