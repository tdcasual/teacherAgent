import type { TeacherMemoryProposal, TeacherMemoryInsightsResponse } from '../../../appTypes'

type MemoryStatusFilter = 'applied' | 'rejected' | 'all'

type TopQueryItem = NonNullable<TeacherMemoryInsightsResponse['top_queries']>[number]

export type MemoryTabProps = {
  memoryStatusFilter: MemoryStatusFilter
  setMemoryStatusFilter: (filter: MemoryStatusFilter) => void
  memoryInsights: TeacherMemoryInsightsResponse | null | undefined
  proposalError: string
  proposalLoading: boolean
  proposals: TeacherMemoryProposal[]
}

export default function MemoryTab({
  memoryStatusFilter,
  setMemoryStatusFilter,
  memoryInsights,
  proposalError,
  proposalLoading,
  proposals,
}: MemoryTabProps) {
  return (
    <section className="grid gap-[10px] p-0 border-none rounded-none bg-transparent shadow-none min-h-0 flex-1 overflow-auto" style={{ overscrollBehavior: 'contain' }}>
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
              {p.reject_reason ? <div className="muted">原因：{p.reject_reason}</div> : null}
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
