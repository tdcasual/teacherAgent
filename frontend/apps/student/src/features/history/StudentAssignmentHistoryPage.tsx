import type { StudentAssignmentHistoryItem } from '../../appTypes'

type StudentAssignmentHistoryPageProps = {
  items: StudentAssignmentHistoryItem[]
  loading: boolean
  error: string
  onBack: () => void
  onSubmit: (assignmentId: string) => void
  onOpenAssignment: (assignmentId: string) => void
}

const canSubmitItem = (item: StudentAssignmentHistoryItem): boolean =>
  item.visibility_status === 'published' && !item.submitted

export default function StudentAssignmentHistoryPage({
  items,
  loading,
  error,
  onBack,
  onSubmit,
  onOpenAssignment,
}: StudentAssignmentHistoryPageProps) {
  return (
    <main className="flex-1 min-h-0 overflow-y-auto bg-[color:var(--color-app-bg)] px-4 py-5 md:px-6 md:py-6" data-testid="student-assignment-history-page">
      <div className="mx-auto grid max-w-[720px] gap-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h1 className="m-0 text-[20px] font-semibold text-ink">作业记录</h1>
          <button type="button" className="student-supporting-link" onClick={onBack}>返回今日</button>
        </div>
        {loading ? <div className="text-xs text-muted">加载中…</div> : null}
        {error ? <div className="text-xs text-muted">{error}</div> : null}
        {!loading && !error && items.length === 0 ? (
          <div className="text-xs text-muted">暂无作业记录</div>
        ) : null}
        {items.map((item) => (
          <article key={item.assignment_id} className="grid gap-2 rounded-[16px] border border-border bg-white px-4 py-3">
            <div className="text-[15px] font-medium text-ink">{item.title}</div>
            <div className="text-[12px] text-muted">
              {item.subject_id} · {item.submitted ? '已提交' : '未提交'}
              {item.visibility_status === 'archived' ? ' · 已归档' : ''}
            </div>
            {item.submitted && item.official_score != null ? (
              <div className="text-[13px] text-ink">官方分 {item.official_score}</div>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="student-supporting-link"
                onClick={() => onOpenAssignment(item.assignment_id)}
              >
                查看材料
              </button>
              {canSubmitItem(item) ? (
                <button
                  type="button"
                  className="inline-flex min-h-[44px] items-center justify-center rounded-[14px] border-none bg-accent px-4 py-2 text-[13px] font-medium text-white"
                  onClick={() => onSubmit(item.assignment_id)}
                >
                  补交 {item.title}
                </button>
              ) : null}
            </div>
          </article>
        ))}
      </div>
    </main>
  )
}
