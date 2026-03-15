import type { StudentTodayHomeViewModel } from '../../appTypes'

type TodayTaskCardProps = {
  viewModel: StudentTodayHomeViewModel
  onPrimaryAction: () => void
}

export default function TodayTaskCard({ viewModel, onPrimaryAction }: TodayTaskCardProps) {
  return (
    <section className="grid gap-4 rounded-[28px] border border-border bg-[color:var(--color-task-strip)] p-6 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center rounded-full border border-border bg-surface-soft px-3 py-1 text-[12px] font-medium text-muted">
          {viewModel.statusLabel}
        </span>
        {viewModel.estimatedMinutes ? (
          <span className="text-[12px] text-muted">预计 {viewModel.estimatedMinutes} 分钟</span>
        ) : null}
        <span className="text-[12px] text-muted">{viewModel.dueLabel}</span>
      </div>
      <div className="grid gap-2">
        <h2 className="m-0 text-[24px] leading-[1.15] font-semibold text-ink">{viewModel.title}</h2>
        <p className="m-0 max-w-[34rem] text-[14px] leading-[1.6] text-muted">{viewModel.summary}</p>
      </div>
      <div>
        <button
          type="button"
          data-testid="student-today-primary-action"
          className="inline-flex min-h-[44px] items-center justify-center rounded-[999px] border-none bg-accent px-5 py-3 text-[14px] font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
          onClick={onPrimaryAction}
          disabled={viewModel.primaryActionDisabled}
        >
          {viewModel.primaryActionLabel}
        </button>
      </div>
    </section>
  )
}
