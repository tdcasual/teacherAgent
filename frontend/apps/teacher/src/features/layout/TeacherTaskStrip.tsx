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
    <section className="rounded-[24px] border border-border bg-[color:var(--color-panel)] px-5 py-4 shadow-sm">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-start">
        <div className="min-w-0 grid gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-semibold tracking-[0.18em] text-muted">
              今日重心
            </span>
            <span className="h-[1px] min-w-[44px] flex-1 bg-[color:var(--color-border)]" aria-hidden="true" />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center rounded-full bg-[color:var(--color-surface-soft)] px-2.5 py-1 text-[11px] font-semibold tracking-[0.12em] text-muted">
              {modeLabel}
            </span>
            <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[12px] font-semibold ${toneClassMap[tone]}`}>
              {statusLabel}
            </span>
          </div>
          <div className="grid gap-1">
            <div className="text-[11px] font-semibold tracking-[0.12em] text-muted">下一步</div>
            <div className="text-[18px] leading-[1.3] font-semibold text-ink">
              {nextStepLabel}
            </div>
          </div>
          <div className="text-[12px] leading-[1.55] text-muted">
            {summary}
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
          <div className="text-[11px] leading-[1.45] text-muted lg:text-right">
            进入工作台继续处理
          </div>
        </div>
      </div>
    </section>
  )
}
