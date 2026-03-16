import type { StudentTodayHomeViewModel } from '../../appTypes'

type TodayTaskCardProps = {
  viewModel: StudentTodayHomeViewModel
  onPrimaryAction: () => void
}

const statusToneClassMap: Record<StudentTodayHomeViewModel['status'], string> = {
  pending_generation: 'border-border bg-surface-soft text-muted',
  generating: 'border-border bg-surface-soft text-muted',
  ready: 'border-border bg-surface-soft text-muted',
  in_progress: 'border-[color:var(--color-accent)] bg-[color:var(--color-accent-soft)] text-[color:var(--color-accent)]',
  submitted: 'border-[color:color-mix(in_oklab,var(--color-success)_35%,white)] bg-[color:color-mix(in_oklab,var(--color-success)_14%,white)] text-[color:var(--color-success)]',
}

export default function TodayTaskCard({ viewModel, onPrimaryAction }: TodayTaskCardProps) {
  return (
    <section className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-center md:gap-4">
      <div className="min-w-0 grid gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`inline-flex items-center rounded-full border px-3 py-1 text-[12px] font-medium ${statusToneClassMap[viewModel.status]}`}>
            {viewModel.statusLabel}
          </span>
        </div>
        <h1 className="m-0 text-[clamp(20px,6vw,30px)] leading-[1.06] font-semibold tracking-[-0.02em] text-ink">
          {viewModel.title}
        </h1>
      </div>
      <div className="md:justify-self-end">
        <button
          type="button"
          data-testid="student-today-primary-action"
          className="inline-flex min-h-[48px] w-full items-center justify-center rounded-[16px] border-none bg-accent px-5 py-3 text-[14px] font-medium text-white shadow-[0_10px_18px_rgba(0,82,204,0.18)] disabled:cursor-not-allowed disabled:opacity-60 md:min-w-[132px] md:w-auto"
          onClick={onPrimaryAction}
          disabled={viewModel.primaryActionDisabled}
        >
          {viewModel.primaryActionLabel}
        </button>
      </div>
    </section>
  )
}
