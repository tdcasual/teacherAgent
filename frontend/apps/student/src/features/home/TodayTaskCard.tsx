import type { StudentTodayHomeViewModel } from '../../appTypes'

type TodayTaskCardProps = {
  viewModel: StudentTodayHomeViewModel
  onPrimaryAction: () => void
}

export default function TodayTaskCard({ viewModel, onPrimaryAction }: TodayTaskCardProps) {
  return (
    <section className="grid gap-5 rounded-[30px] border border-[color:color-mix(in_oklab,var(--color-accent)_12%,var(--color-border))] bg-[color:var(--color-task-strip)] p-6 shadow-[0_12px_30px_rgba(148,163,184,0.14)]">
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center rounded-full bg-[color:color-mix(in_oklab,var(--color-accent-soft)_78%,white)] px-3 py-1 text-[11px] font-semibold tracking-[0.12em] text-[color:var(--color-accent)]">
          主任务
        </span>
        <span className="inline-flex items-center rounded-full border border-border bg-surface-soft px-3 py-1 text-[12px] font-medium text-muted">
          {viewModel.statusLabel}
        </span>
        {viewModel.estimatedMinutes ? (
          <span className="text-[12px] text-muted">预计 {viewModel.estimatedMinutes} 分钟</span>
        ) : null}
        <span className="text-[12px] text-muted">{viewModel.dueLabel}</span>
      </div>
      <div className="grid gap-2">
        <h2 className="m-0 text-[clamp(26px,3.8vw,34px)] leading-[1.08] font-semibold text-ink">{viewModel.title}</h2>
        <p className="m-0 max-w-[34rem] text-[14px] leading-[1.6] text-muted">{viewModel.summary}</p>
      </div>
      <div className="grid gap-2 md:grid-cols-[auto_1fr] md:items-end">
        <button
          type="button"
          data-testid="student-today-primary-action"
          className="inline-flex min-h-[48px] items-center justify-center rounded-[999px] border-none bg-accent px-5 py-3 text-[14px] font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
          onClick={onPrimaryAction}
          disabled={viewModel.primaryActionDisabled}
        >
          {viewModel.primaryActionLabel}
        </button>
        <div className="text-[12px] leading-[1.5] text-muted md:text-right">
          保持今天只做一件主任务，材料和历史入口放到下面再看。
        </div>
      </div>
    </section>
  )
}
