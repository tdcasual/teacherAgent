import { useState } from 'react'

import type {
  StudentMemoryInsightsResponse,
  StudentMemoryProposal,
  TeacherMemoryInsightsResponse,
  TeacherMemoryProposal,
} from '../../../appTypes'

type MemoryStatusFilter = 'applied' | 'rejected' | 'all'
type StudentMemoryStatusFilter = 'proposed' | 'applied' | 'rejected' | 'all'

type TopQueryItem = NonNullable<TeacherMemoryInsightsResponse['top_queries']>[number]

const studentMemoryTypeLabel = (value: string) => {
  const key = String(value || '').trim().toLowerCase()
  if (key === 'learning_preference') return '学习偏好'
  if (key === 'stable_misconception') return '稳定误区'
  if (key === 'long_term_goal') return '长期目标'
  if (key === 'effective_intervention') return '有效干预'
  return key || '未分类'
}

const studentMemoryStatusLabel = (value: string) => {
  const key = String(value || '').trim().toLowerCase()
  if (key === 'applied') return '已通过'
  if (key === 'rejected') return '已拒绝'
  if (key === 'deleted') return '已删除'
  return '待审核'
}

const studentMemoryStatusClass = (value: string) => {
  const key = String(value || '').trim().toLowerCase()
  if (key === 'applied') return 'text-[#1f6b57] bg-[#e9f6f1] border-[#b8e3d4]'
  if (key === 'rejected') return 'text-[#8a1f1f] bg-[#ffe8e6] border-[#f4b9b3]'
  if (key === 'deleted') return 'text-[#6c6f7a] bg-[#f2f3f5] border-[#d7dae0]'
  return 'text-[#815900] bg-[#fff7df] border-[#efd58f]'
}

const statusCount = (insights: StudentMemoryInsightsResponse | null | undefined, status: string) => {
  const raw = insights?.status_counts?.[status]
  return Number.isFinite(raw) ? Number(raw) : 0
}

const typeCountItems = (insights: StudentMemoryInsightsResponse | null | undefined) => {
  const source = insights?.type_counts
  if (!source || typeof source !== 'object') return []
  return Object.entries(source)
    .map(([key, value]) => ({ key, value: Number(value || 0) }))
    .filter((item) => Number.isFinite(item.value) && item.value > 0)
    .sort((a, b) => b.value - a.value)
    .slice(0, 4)
}

export type MemoryTabProps = {
  memoryStatusFilter: MemoryStatusFilter
  setMemoryStatusFilter: (filter: MemoryStatusFilter) => void
  memoryInsights: TeacherMemoryInsightsResponse | null | undefined
  proposalError: string
  proposalLoading: boolean
  proposals: TeacherMemoryProposal[]
  onDeleteProposal: (proposalId: string) => Promise<void>

  studentMemoryStatusFilter: StudentMemoryStatusFilter
  setStudentMemoryStatusFilter: (filter: StudentMemoryStatusFilter) => void
  studentMemoryStudentFilter: string
  setStudentMemoryStudentFilter: (studentId: string) => void
  studentMemoryInsights: StudentMemoryInsightsResponse | null | undefined
  studentProposalError: string
  studentProposalLoading: boolean
  studentProposals: StudentMemoryProposal[]
  onReviewStudentProposal: (proposalId: string, approve: boolean) => Promise<void>
  onDeleteStudentProposal: (proposalId: string) => Promise<void>
}

export default function MemoryTab({
  memoryStatusFilter,
  setMemoryStatusFilter,
  memoryInsights,
  proposalError,
  proposalLoading,
  proposals,
  onDeleteProposal,
  studentMemoryStatusFilter,
  setStudentMemoryStatusFilter,
  studentMemoryStudentFilter,
  setStudentMemoryStudentFilter,
  studentMemoryInsights,
  studentProposalError,
  studentProposalLoading,
  studentProposals,
  onReviewStudentProposal,
  onDeleteStudentProposal,
}: MemoryTabProps) {
  const [deletingProposalId, setDeletingProposalId] = useState('')
  const [deleteError, setDeleteError] = useState('')
  const [reviewingStudentProposalId, setReviewingStudentProposalId] = useState('')
  const [deletingStudentProposalId, setDeletingStudentProposalId] = useState('')
  const [studentActionError, setStudentActionError] = useState('')

  const handleDeleteProposal = async (proposalId: string) => {
    const pid = String(proposalId || '').trim()
    if (!pid) return
    const confirmed = window.confirm('确认删除这条自动记忆记录？删除后将不再用于自动记忆检索。')
    if (!confirmed) return
    setDeleteError('')
    setDeletingProposalId(pid)
    try {
      await onDeleteProposal(pid)
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error || '删除失败')
      setDeleteError(message)
    } finally {
      setDeletingProposalId('')
    }
  }

  const handleReviewStudentProposal = async (proposalId: string, approve: boolean) => {
    const pid = String(proposalId || '').trim()
    if (!pid) return
    setStudentActionError('')
    setReviewingStudentProposalId(pid)
    try {
      await onReviewStudentProposal(pid, approve)
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error || '审核失败')
      setStudentActionError(message)
    } finally {
      setReviewingStudentProposalId('')
    }
  }

  const handleDeleteStudentProposal = async (proposalId: string) => {
    const pid = String(proposalId || '').trim()
    if (!pid) return
    const confirmed = window.confirm('确认删除这条学生记忆提案？')
    if (!confirmed) return
    setStudentActionError('')
    setDeletingStudentProposalId(pid)
    try {
      await onDeleteStudentProposal(pid)
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error || '删除失败')
      setStudentActionError(message)
    } finally {
      setDeletingStudentProposalId('')
    }
  }

  return (
    <section className="grid gap-[12px] p-0 border-none rounded-none bg-transparent shadow-none min-h-0 flex-1 overflow-auto" style={{ overscrollBehavior: 'contain' }}>
      <div className="grid gap-[10px] rounded-[14px] border border-border bg-white p-[10px_12px]">
        <div className="flex justify-between items-center gap-3">
          <strong>自动记忆记录</strong>
          <div className="flex gap-2 items-center">
            <div className="view-switch">
              <button
                type="button"
                className={memoryStatusFilter === 'applied' ? 'active' : ''}
                onClick={() => setMemoryStatusFilter('applied')}
              >
                已写入
              </button>
              <button
                type="button"
                className={memoryStatusFilter === 'rejected' ? 'active' : ''}
                onClick={() => setMemoryStatusFilter('rejected')}
              >
                已拦截
              </button>
              <button
                type="button"
                className={memoryStatusFilter === 'all' ? 'active' : ''}
                onClick={() => setMemoryStatusFilter('all')}
              >
                全部
              </button>
            </div>
          </div>
        </div>
        {memoryInsights?.summary && (
          <div className="grid grid-cols-3 gap-2 max-[900px]:grid-cols-2">
            <div className="border border-border rounded-xl bg-white p-[8px_10px]">
              <div className="text-[16px] font-bold text-ink">{memoryInsights.summary.active_total ?? 0}</div>
              <div className="mt-0.5 text-[11px] text-muted">活跃记忆</div>
            </div>
            <div className="border border-border rounded-xl bg-white p-[8px_10px]">
              <div className="text-[16px] font-bold text-ink">{memoryInsights.summary.expired_total ?? 0}</div>
              <div className="mt-0.5 text-[11px] text-muted">已过期</div>
            </div>
            <div className="border border-border rounded-xl bg-white p-[8px_10px]">
              <div className="text-[16px] font-bold text-ink">{memoryInsights.summary.superseded_total ?? 0}</div>
              <div className="mt-0.5 text-[11px] text-muted">已替代</div>
            </div>
            <div className="border border-border rounded-xl bg-white p-[8px_10px]">
              <div className="text-[16px] font-bold text-ink">{memoryInsights.summary.avg_priority_active ?? 0}</div>
              <div className="mt-0.5 text-[11px] text-muted">平均优先级</div>
            </div>
            <div className="border border-border rounded-xl bg-white p-[8px_10px]">
              <div className="text-[16px] font-bold text-ink">
                {`${Math.round((memoryInsights.retrieval?.search_hit_rate ?? 0) * 100)}%`}
              </div>
              <div className="mt-0.5 text-[11px] text-muted">检索命中率(14d)</div>
            </div>
            <div className="border border-border rounded-xl bg-white p-[8px_10px]">
              <div className="text-[16px] font-bold text-ink">{memoryInsights.retrieval?.search_calls ?? 0}</div>
              <div className="mt-0.5 text-[11px] text-muted">检索次数(14d)</div>
            </div>
          </div>
        )}
        {Array.isArray(memoryInsights?.top_queries) && (memoryInsights?.top_queries || []).length > 0 && (
          <div className="grid gap-1.5 border border-dashed border-border rounded-xl p-[8px_10px] bg-white/70">
            <div className="muted">高频命中查询（14天）</div>
            {(memoryInsights?.top_queries || []).slice(0, 5).map((q: TopQueryItem) => (
              <div key={q.query} className="text-[12px] text-muted flex justify-between gap-2 flex-wrap">
                <span>{q.query}</span>
                <span>
                  {q.hit_calls}/{q.calls}
                </span>
              </div>
            ))}
          </div>
        )}
        {proposalError ? <div className="status err">{proposalError}</div> : null}
        {deleteError ? <div className="status err">{deleteError}</div> : null}
        {!proposalLoading && proposals.length === 0 ? <div className="text-[12px] text-muted">暂无记录。</div> : null}
        {proposals.length > 0 && (
          <div className="grid gap-[10px]">
            {proposals.map((p) => (
              <div key={p.proposal_id} className="border border-border rounded-[14px] bg-white p-[10px_12px] grid gap-2">
                <div className="font-semibold">
                  {p.title || 'Memory Update'} <span className="muted">[{p.target || 'MEMORY'}]</span>
                </div>
                <div className="text-[12px] text-muted flex justify-between gap-2 flex-wrap">
                  <span>{p.created_at || '-'}</span>
                  <span>{p.source || 'manual'}</span>
                  <span className={`rounded-lg px-2 py-0.5 text-[11px] border ${
                    String(p.status || '').toLowerCase() === 'applied'
                      ? 'text-[#1f6b57] bg-[#e9f6f1] border-[#b8e3d4]'
                      : String(p.status || '').toLowerCase() === 'rejected'
                        ? 'text-[#8a1f1f] bg-[#ffe8e6] border-[#f4b9b3]'
                        : 'text-muted bg-white border-border'
                  }`}>
                    {String(p.status || '').toLowerCase() === 'applied'
                      ? '已写入'
                      : String(p.status || '').toLowerCase() === 'rejected'
                        ? '已拦截'
                        : '待处理'}
                  </span>
                </div>
                <div className="text-[13px] leading-[1.45] whitespace-pre-wrap">{p.content || ''}</div>
                <div className="text-[12px] text-muted flex justify-between gap-2 flex-wrap">
                  <span>{p.proposal_id}</span>
                  <span>{p.applied_at || p.rejected_at || '-'}</span>
                </div>
                <div className="flex justify-end">
                  <button
                    type="button"
                    className="ghost"
                    onClick={() => {
                      void handleDeleteProposal(p.proposal_id)
                    }}
                    disabled={Boolean(deletingProposalId)}
                  >
                    {deletingProposalId === p.proposal_id ? '删除中…' : '删除'}
                  </button>
                </div>
                {p.reject_reason ? <div className="muted">原因：{p.reject_reason}</div> : null}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="grid gap-[10px] rounded-[14px] border border-border bg-white p-[10px_12px]">
        <div className="flex justify-between items-center gap-3 flex-wrap">
          <strong>学生记忆提案（受控写入）</strong>
          <div className="view-switch">
            <button
              type="button"
              className={studentMemoryStatusFilter === 'proposed' ? 'active' : ''}
              onClick={() => setStudentMemoryStatusFilter('proposed')}
            >
              待审核
            </button>
            <button
              type="button"
              className={studentMemoryStatusFilter === 'applied' ? 'active' : ''}
              onClick={() => setStudentMemoryStatusFilter('applied')}
            >
              已通过
            </button>
            <button
              type="button"
              className={studentMemoryStatusFilter === 'rejected' ? 'active' : ''}
              onClick={() => setStudentMemoryStatusFilter('rejected')}
            >
              已拒绝
            </button>
            <button
              type="button"
              className={studentMemoryStatusFilter === 'all' ? 'active' : ''}
              onClick={() => setStudentMemoryStatusFilter('all')}
            >
              全部
            </button>
          </div>
        </div>

        <div className="grid gap-2">
          <input
            type="text"
            className="w-full rounded-lg border border-border bg-white px-3 py-2 text-[12px]"
            placeholder="按学生ID过滤（可选）"
            value={studentMemoryStudentFilter}
            onChange={(event) => setStudentMemoryStudentFilter(event.target.value)}
          />
        </div>

        {studentMemoryInsights ? (
          <div className="grid grid-cols-4 gap-2 max-[900px]:grid-cols-2">
            <div className="border border-border rounded-xl bg-white p-[8px_10px]">
              <div className="text-[16px] font-bold text-ink">{studentMemoryInsights.total ?? 0}</div>
              <div className="mt-0.5 text-[11px] text-muted">提案总数(14d)</div>
            </div>
            <div className="border border-border rounded-xl bg-white p-[8px_10px]">
              <div className="text-[16px] font-bold text-ink">{statusCount(studentMemoryInsights, 'proposed')}</div>
              <div className="mt-0.5 text-[11px] text-muted">待审核</div>
            </div>
            <div className="border border-border rounded-xl bg-white p-[8px_10px]">
              <div className="text-[16px] font-bold text-ink">{statusCount(studentMemoryInsights, 'applied')}</div>
              <div className="mt-0.5 text-[11px] text-muted">已通过</div>
            </div>
            <div className="border border-border rounded-xl bg-white p-[8px_10px]">
              <div className="text-[16px] font-bold text-ink">{statusCount(studentMemoryInsights, 'rejected')}</div>
              <div className="mt-0.5 text-[11px] text-muted">已拒绝</div>
            </div>
          </div>
        ) : null}

        {typeCountItems(studentMemoryInsights).length > 0 ? (
          <div className="grid gap-1.5 border border-dashed border-border rounded-xl p-[8px_10px] bg-white/70">
            <div className="muted">类型分布（14天）</div>
            {typeCountItems(studentMemoryInsights).map((item) => (
              <div key={item.key} className="text-[12px] text-muted flex justify-between gap-2 flex-wrap">
                <span>{studentMemoryTypeLabel(item.key)}</span>
                <span>{item.value}</span>
              </div>
            ))}
          </div>
        ) : null}

        {studentProposalError ? <div className="status err">{studentProposalError}</div> : null}
        {studentActionError ? <div className="status err">{studentActionError}</div> : null}
        {!studentProposalLoading && studentProposals.length === 0 ? (
          <div className="text-[12px] text-muted">暂无学生记忆提案。</div>
        ) : null}

        {studentProposals.length > 0 ? (
          <div className="grid gap-[10px]">
            {studentProposals.map((proposal) => {
              const status = String(proposal.status || '').toLowerCase()
              const isProposed = status === 'proposed' || !status
              const isReviewingThis = reviewingStudentProposalId === proposal.proposal_id
              const isDeletingThis = deletingStudentProposalId === proposal.proposal_id
              const busy = Boolean(reviewingStudentProposalId || deletingStudentProposalId)

              return (
                <div key={proposal.proposal_id} className="border border-border rounded-[14px] bg-white p-[10px_12px] grid gap-2">
                  <div className="font-semibold flex justify-between gap-2 flex-wrap items-center">
                    <span>{studentMemoryTypeLabel(proposal.memory_type || '')}</span>
                    <span className={`rounded-lg px-2 py-0.5 text-[11px] border ${studentMemoryStatusClass(status)}`}>
                      {studentMemoryStatusLabel(status)}
                    </span>
                  </div>

                  <div className="text-[12px] text-muted flex justify-between gap-2 flex-wrap">
                    <span>学生：{proposal.student_id || '-'}</span>
                    <span>{proposal.created_at || '-'}</span>
                    <span>{proposal.source || 'manual'}</span>
                  </div>

                  <div className="text-[13px] leading-[1.45] whitespace-pre-wrap">{proposal.content || ''}</div>

                  {Array.isArray(proposal.evidence_refs) && proposal.evidence_refs.length > 0 ? (
                    <div className="text-[12px] text-muted break-all">
                      证据：{proposal.evidence_refs.join('，')}
                    </div>
                  ) : null}

                  {Array.isArray(proposal.risk_flags) && proposal.risk_flags.length > 0 ? (
                    <div className="text-[12px] text-[#8a1f1f] break-all">
                      风险标记：{proposal.risk_flags.join('，')}
                    </div>
                  ) : null}

                  <div className="text-[12px] text-muted flex justify-between gap-2 flex-wrap">
                    <span>{proposal.proposal_id}</span>
                    <span>{proposal.reviewed_at || proposal.deleted_at || '-'}</span>
                  </div>

                  <div className="flex justify-end gap-2 flex-wrap">
                    {isProposed ? (
                      <>
                        <button
                          type="button"
                          className="ghost"
                          disabled={busy}
                          onClick={() => {
                            void handleReviewStudentProposal(proposal.proposal_id, true)
                          }}
                        >
                          {isReviewingThis ? '处理中…' : '通过'}
                        </button>
                        <button
                          type="button"
                          className="ghost"
                          disabled={busy}
                          onClick={() => {
                            void handleReviewStudentProposal(proposal.proposal_id, false)
                          }}
                        >
                          {isReviewingThis ? '处理中…' : '拒绝'}
                        </button>
                      </>
                    ) : null}
                    <button
                      type="button"
                      className="ghost"
                      disabled={busy}
                      onClick={() => {
                        void handleDeleteStudentProposal(proposal.proposal_id)
                      }}
                    >
                      {isDeletingThis ? '删除中…' : '删除'}
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        ) : null}
      </div>
    </section>
  )
}
