import { useCallback } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import {
  createRoutingProposal,
  fetchRoutingProposalDetail,
  reviewRoutingProposal,
  rollbackRoutingConfig,
  simulateRouting,
} from './routingApi'
import type { RoutingConfig, RoutingProposalDetail, RoutingSimulateResult } from './routingTypes'

type LoadOverviewFn = (options?: { silent?: boolean; forceReplaceDraft?: boolean }) => Promise<void>

type Props = {
  apiBase: string
  teacherId: string
  isLegacyFlat: boolean
  draft: RoutingConfig
  proposalNote: string
  rollbackNote: string
  simRole: string
  simSkillId: string
  simKind: string
  simNeedsTools: boolean
  simNeedsJson: boolean
  expandedProposalIds: Record<string, boolean>
  proposalDetails: Record<string, RoutingProposalDetail>
  proposalLoadingMap: Record<string, boolean>
  loadOverview: LoadOverviewFn
  setBusy: Dispatch<SetStateAction<boolean>>
  setStatus: Dispatch<SetStateAction<string>>
  setError: Dispatch<SetStateAction<string>>
  setSimResult: Dispatch<SetStateAction<RoutingSimulateResult | null>>
  setProposalNote: Dispatch<SetStateAction<string>>
  setShowManualReview: Dispatch<SetStateAction<boolean>>
  setExpandedProposalIds: Dispatch<SetStateAction<Record<string, boolean>>>
  setProposalDetails: Dispatch<SetStateAction<Record<string, RoutingProposalDetail>>>
  setProposalLoadingMap: Dispatch<SetStateAction<Record<string, boolean>>>
  setRollbackVersion: Dispatch<SetStateAction<string>>
  setRollbackNote: Dispatch<SetStateAction<string>>
}

export function useRoutingProposalActions({
  apiBase,
  teacherId,
  isLegacyFlat,
  draft,
  proposalNote,
  rollbackNote,
  simRole,
  simSkillId,
  simKind,
  simNeedsTools,
  simNeedsJson,
  expandedProposalIds,
  proposalDetails,
  proposalLoadingMap,
  loadOverview,
  setBusy,
  setStatus,
  setError,
  setSimResult,
  setProposalNote,
  setShowManualReview,
  setExpandedProposalIds,
  setProposalDetails,
  setProposalLoadingMap,
  setRollbackVersion,
  setRollbackNote,
}: Props) {
  const handleSimulate = useCallback(async () => {
    setBusy(true)
    setStatus('')
    setError('')
    try {
      const result = await simulateRouting(apiBase, {
        teacher_id: teacherId || undefined,
        role: simRole || undefined,
        skill_id: simSkillId || undefined,
        kind: simKind || undefined,
        needs_tools: simNeedsTools,
        needs_json: simNeedsJson,
        config: draft as unknown as Record<string, unknown>,
      })
      setSimResult(result)
      setStatus('仿真完成。')
    } catch (err) {
      setError((err as Error).message || '仿真失败')
    } finally {
      setBusy(false)
    }
  }, [apiBase, draft, setBusy, setError, setSimResult, setStatus, simKind, simNeedsJson, simNeedsTools, simRole, simSkillId, teacherId])

  const handlePropose = useCallback(async () => {
    setBusy(true)
    setStatus('')
    setError('')
    try {
      const created = await createRoutingProposal(apiBase, {
        teacher_id: teacherId || undefined,
        note: proposalNote || undefined,
        config: draft as unknown as Record<string, unknown>,
      })
      if (!created.ok) throw new Error(created.error ? JSON.stringify(created.error) : '提案创建失败')

      const proposalId = String(created.proposal_id || '').trim()
      if (!proposalId) throw new Error('提案创建成功但未返回 proposal_id')

      if (isLegacyFlat) {
        setStatus(`提案已创建：${proposalId}`)
        setProposalNote('')
        setShowManualReview(true)
        await loadOverview({ silent: true })
        return
      }

      const applied = await reviewRoutingProposal(apiBase, proposalId, {
        teacher_id: teacherId || undefined,
        approve: true,
      })
      if (!applied.ok) throw new Error(applied.error ? JSON.stringify(applied.error) : '自动生效失败')

      const nextVersion = Number(applied.version || 0)
      const versionText = Number.isFinite(nextVersion) && nextVersion > 0 ? `v${nextVersion}` : '最新版本'
      setStatus(`配置已生效（${versionText}）`)
      setProposalNote('')
      setExpandedProposalIds((prev) => ({ ...prev, [proposalId]: false }))
      await loadOverview({ silent: true, forceReplaceDraft: true })
    } catch (err) {
      setError((err as Error).message || '保存并生效失败')
    } finally {
      setBusy(false)
    }
  }, [
    apiBase,
    draft,
    isLegacyFlat,
    loadOverview,
    proposalNote,
    setBusy,
    setError,
    setExpandedProposalIds,
    setProposalNote,
    setShowManualReview,
    setStatus,
    teacherId,
  ])

  const handleReviewProposal = useCallback(async (proposalId: string, approve: boolean) => {
    setBusy(true)
    setStatus('')
    setError('')
    try {
      const result = await reviewRoutingProposal(apiBase, proposalId, {
        teacher_id: teacherId || undefined,
        approve,
      })
      if (!result.ok) throw new Error(result.error ? JSON.stringify(result.error) : '审核失败')
      setStatus(approve ? `提案 ${proposalId} 已生效` : `提案 ${proposalId} 已拒绝`)
      setExpandedProposalIds((prev) => ({ ...prev, [proposalId]: false }))
      await loadOverview({ silent: true, forceReplaceDraft: approve })
    } catch (err) {
      setError((err as Error).message || '提案审核失败')
    } finally {
      setBusy(false)
    }
  }, [apiBase, loadOverview, setBusy, setError, setExpandedProposalIds, setStatus, teacherId])

  const handleToggleProposalDetail = useCallback(async (proposalId: string) => {
    const nextExpanded = !Boolean(expandedProposalIds[proposalId])
    setExpandedProposalIds((prev) => ({ ...prev, [proposalId]: nextExpanded }))
    if (!nextExpanded) return
    if (proposalDetails[proposalId] || proposalLoadingMap[proposalId]) return
    setProposalLoadingMap((prev) => ({ ...prev, [proposalId]: true }))
    setError('')
    try {
      const detail = await fetchRoutingProposalDetail(apiBase, proposalId, teacherId || undefined)
      setProposalDetails((prev) => ({ ...prev, [proposalId]: detail }))
    } catch (err) {
      setError((err as Error).message || '提案详情加载失败')
    } finally {
      setProposalLoadingMap((prev) => ({ ...prev, [proposalId]: false }))
    }
  }, [
    apiBase,
    expandedProposalIds,
    proposalDetails,
    proposalLoadingMap,
    setError,
    setExpandedProposalIds,
    setProposalDetails,
    setProposalLoadingMap,
    teacherId,
  ])

  const handleRollback = useCallback(async (targetVersion: number) => {
    if (!Number.isFinite(targetVersion) || targetVersion <= 0) {
      setError('回滚版本号无效')
      return
    }
    setBusy(true)
    setStatus('')
    setError('')
    try {
      const result = await rollbackRoutingConfig(apiBase, {
        teacher_id: teacherId || undefined,
        target_version: targetVersion,
        note: rollbackNote || undefined,
      })
      if (!result.ok) throw new Error(result.error || '回滚失败')
      setStatus(`已回滚到版本 ${targetVersion}`)
      setRollbackVersion('')
      setRollbackNote('')
      await loadOverview({ silent: true, forceReplaceDraft: true })
    } catch (err) {
      setError((err as Error).message || '回滚失败')
    } finally {
      setBusy(false)
    }
  }, [apiBase, loadOverview, rollbackNote, setBusy, setError, setRollbackNote, setRollbackVersion, setStatus, teacherId])

  return {
    handleSimulate,
    handlePropose,
    handleReviewProposal,
    handleToggleProposalDetail,
    handleRollback,
  }
}
