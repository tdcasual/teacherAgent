import type { WorkflowIndicatorTone } from '../../appTypes'

type TeacherTaskStripProps = {
  mode: 'assignment' | 'exam'
  statusLabel: string
  tone: WorkflowIndicatorTone
  summary: string
  nextStepLabel: string
  primaryActionLabel: string
  onPrimaryAction: () => void
  primaryActionDisabled?: boolean
}

const toneClassMap: Record<WorkflowIndicatorTone, string> = {
  neutral: 'border-border bg-surface-soft text-muted',
  active: 'border-[color:var(--color-accent)] bg-[color:var(--color-accent-soft)] text-[color:var(--color-accent)]',
  success: 'border-[color:var(--color-success)] bg-[color:var(--color-success-soft)] text-[color:var(--color-success)]',
  error: 'border-[color:var(--color-danger)] bg-danger-soft text-danger',
}

export default function TeacherTaskStrip({
  mode,
  statusLabel,
  tone,
  nextStepLabel,
  primaryActionLabel,
  onPrimaryAction,
  primaryActionDisabled = false,
}: TeacherTaskStripProps) {
  const modeLabel = mode === 'assignment' ? '今日作业' : '今日考试'
  const displayNextStep = nextStepLabel.replace(/^下一步[:：]\s*/, '')

  return (
    <section className="rounded-[24px] border border-border bg-[color:var(--color-panel)] px-5 py-4 shadow-sm">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
        <div className="min-w-0 grid gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center rounded-full bg-[color:var(--color-surface-soft)] px-2.5 py-1 text-[11px] font-semibold tracking-[0.12em] text-muted">
              {modeLabel}
            </span>
            <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[12px] font-semibold ${toneClassMap[tone]}`}>
              {statusLabel}
            </span>
          </div>
          <div className="text-[clamp(22px,2vw,30px)] leading-[1.18] font-semibold text-ink">
            {displayNextStep}
          </div>
        </div>
        <div className="flex w-full flex-col items-stretch gap-2 lg:w-auto lg:min-w-[148px]">
          <button
            type="button"
            className="border-none rounded-[16px] py-[11px] px-[16px] bg-accent text-white cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed shrink-0"
            onClick={onPrimaryAction}
            disabled={primaryActionDisabled}
          >
            {primaryActionLabel}
          </button>
        </div>
      </div>
    </section>
  )
}
