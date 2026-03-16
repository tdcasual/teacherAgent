import type { WorkflowSummaryCardProps } from '../../../types/workflow'
import type { WorkflowStepItem } from '../../../appTypes'
import { buildTeacherWorkflowGuidance, findActiveWorkflowStep } from '../workflowIndicators'

export default function WorkflowSummaryCard(props: WorkflowSummaryCardProps) {
  const {
    uploadMode,
    setUploadMode,
    activeWorkflowIndicator,
    formatProgressSummary,
    scrollToWorkflowSection,
    refreshWorkflowWorkbench,
    progressData,
    progressAssignmentId,
    progressLoading,
    fetchAssignmentProgress,
  } = props
  const activeStep = findActiveWorkflowStep(activeWorkflowIndicator)
  const guidance = buildTeacherWorkflowGuidance({
    mode: uploadMode === 'exam' ? 'exam' : 'assignment',
    tone: activeWorkflowIndicator.tone,
    activeStepKey: activeStep?.key,
    hasExecutionTimeline: false,
    hasProgressData: Boolean(progressData),
  })
  const actionTargetLabel = activeStep?.label || (uploadMode === 'assignment' ? '上传文件' : '上传考试材料')

  return (
    <div className="grid gap-2.5">
      <section className="workflow-summary-card grid gap-3 rounded-[18px] border border-[color:color-mix(in_oklab,var(--color-border)_74%,white)] bg-[color:color-mix(in_oklab,var(--color-panel)_86%,white)] p-[12px] shadow-none">
        <div className="grid gap-3">
          <div className="grid gap-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <div className="segmented inline-flex border border-border rounded-lg overflow-hidden bg-white shrink-0">
                <button type="button" className={`border-0 bg-transparent py-1.5 px-3 cursor-pointer text-[12px] text-muted ${uploadMode === 'assignment' ? 'active bg-accent-soft text-accent font-semibold' : ''}`} onClick={() => setUploadMode('assignment')}>
                  作业
                </button>
                <button type="button" className={`border-0 bg-transparent py-1.5 px-3 cursor-pointer text-[12px] text-muted border-l border-border ${uploadMode === 'exam' ? 'active bg-accent-soft text-accent font-semibold' : ''}`} onClick={() => setUploadMode('exam')}>
                  考试
                </button>
              </div>
              <span data-testid="workflow-summary-status-chip" className={`workflow-chip inline-flex items-center px-2 py-0.5 rounded-lg text-[12px] font-semibold border ${
                activeWorkflowIndicator.tone === 'active'
                  ? 'active text-accent border-[color:color-mix(in_oklab,var(--color-accent)_24%,white)] bg-accent-soft'
                  : activeWorkflowIndicator.tone === 'success'
                    ? 'success text-success border-[color:color-mix(in_oklab,var(--color-success)_24%,white)] bg-success-soft'
                    : activeWorkflowIndicator.tone === 'error'
                      ? 'error text-danger border-[color:color-mix(in_oklab,var(--color-danger)_18%,white)] bg-danger-soft'
                  : 'text-muted border-border bg-surface-soft'
              }`}>{activeWorkflowIndicator.label}</span>
            </div>
            <div className="text-[17px] leading-[1.25] font-semibold text-ink">{actionTargetLabel}</div>
          </div>
          <button
            type="button"
            className="inline-flex w-full items-center justify-center rounded-xl border-none bg-accent px-[14px] py-[10px] text-white cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed shrink-0"
            onClick={() => scrollToWorkflowSection(guidance.primaryActionTargetId)}
          >
            {guidance.primaryActionLabel}
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {activeWorkflowIndicator.steps.map((step: WorkflowStepItem) => (
            <div key={step.key} className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1.5 text-[12px] ${
              step.state === 'done'
                ? 'text-success border-[color:color-mix(in_oklab,var(--color-success)_24%,white)] bg-success-soft'
                : step.state === 'active'
                  ? 'text-accent border-[color:color-mix(in_oklab,var(--color-accent)_24%,white)] bg-accent-soft'
                  : step.state === 'error'
                    ? 'text-danger border-[color:color-mix(in_oklab,var(--color-danger)_18%,white)] bg-danger-soft'
                    : 'text-muted border-[color:color-mix(in_oklab,var(--color-border)_88%,white)] bg-[color:color-mix(in_oklab,var(--color-surface-soft)_72%,white)]'
              }`}>
              <span className={`w-2 h-2 rounded-full shrink-0 ${
                step.state === 'done'
                  ? 'bg-success'
                  : step.state === 'active'
                    ? 'bg-accent'
                  : step.state === 'error'
                    ? 'bg-danger'
                    : 'bg-border-strong'
              } ${step.state === 'active' ? 'shadow-[0_0_0_3px_rgba(0,82,204,0.14)]' : ''}`} />
              <span>{step.label}</span>
            </div>
          ))}
        </div>
        <div className="flex flex-wrap gap-2 border-t border-[color:color-mix(in_oklab,var(--color-border)_72%,white)] pt-3">
          <button type="button" className="ghost" onClick={() => scrollToWorkflowSection('workflow-upload-section')}>
            查看上传区
          </button>
          <button type="button" className="ghost" onClick={refreshWorkflowWorkbench}>
            刷新状态
          </button>
        </div>
      </section>
      {uploadMode === 'assignment' ? (
        <section className="grid gap-2 rounded-[16px] bg-[color:color-mix(in_oklab,var(--color-surface-soft)_78%,white)] px-[12px] py-[10px] ring-1 ring-inset ring-[color:color-mix(in_oklab,var(--color-border)_70%,white)]">
          <div className="text-muted text-[12px]">完成情况速览</div>
          <div className="text-[12px] leading-[1.45] text-[color:color-mix(in_oklab,var(--color-ink)_82%,white)]">{formatProgressSummary(progressData, progressAssignmentId)}</div>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="ghost" onClick={() => scrollToWorkflowSection('workflow-progress-section')}>
              查看完成情况
            </button>
            <button type="button" className="ghost" disabled={progressLoading} onClick={() => void fetchAssignmentProgress()}>
              {progressLoading ? '加载中…' : '刷新完成率'}
            </button>
          </div>
        </section>
      ) : null}
    </div>
  )
}
