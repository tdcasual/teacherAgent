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
  summary,
  nextStepLabel,
  primaryActionLabel,
  onPrimaryAction,
  primaryActionDisabled = false,
}: TeacherTaskStripProps) {
  const modeLabel = mode === 'assignment' ? '今日作业流程' : '今日考试流程'

  return (
    <section className="rounded-[18px] border border-border bg-[color:var(--color-panel)] px-4 py-3 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-semibold tracking-[0.12em] text-muted">
              {modeLabel}
            </span>
            <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[12px] font-semibold ${toneClassMap[tone]}`}>
              {statusLabel}
            </span>
          </div>
          <div className="mt-2 text-[15px] font-semibold text-ink">
            {nextStepLabel}
          </div>
          <div className="mt-1 text-[12px] leading-[1.45] text-muted">
            {summary}
          </div>
        </div>
        <button
          type="button"
          className="border-none rounded-xl py-[10px] px-[14px] bg-accent text-white cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed shrink-0"
          onClick={onPrimaryAction}
          disabled={primaryActionDisabled}
        >
          {primaryActionLabel}
        </button>
      </div>
    </section>
  )
}
