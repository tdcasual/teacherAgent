import type { WorkflowSummaryCardProps } from '../../../types/workflow'
import type { WorkflowStepItem } from '../../../appTypes'

export default function WorkflowSummaryCard(props: WorkflowSummaryCardProps) {
  const {
    uploadMode,
    setUploadMode,
    activeWorkflowIndicator,
    formatUploadJobSummary,
    formatExamJobSummary,
    formatProgressSummary,
    uploadJobInfo,
    uploadAssignmentId,
    examJobInfo,
    examId,
    scrollToWorkflowSection,
    refreshWorkflowWorkbench,
    progressData,
    progressAssignmentId,
    progressLoading,
    fetchAssignmentProgress,
  } = props

  return (
    <>
                    <div className="workflow-summary-card border border-border rounded-[14px] bg-white p-[10px] grid gap-2">
                      <div className="segmented inline-flex border border-border rounded-lg overflow-hidden bg-white shrink-0">
                        <button type="button" className={`border-0 bg-transparent py-1.5 px-3 cursor-pointer text-[12px] text-muted ${uploadMode === 'assignment' ? 'active bg-accent-soft text-accent font-semibold' : ''}`} onClick={() => setUploadMode('assignment')}>
                          作业
                        </button>
                        <button type="button" className={`border-0 bg-transparent py-1.5 px-3 cursor-pointer text-[12px] text-muted border-l border-border ${uploadMode === 'exam' ? 'active bg-accent-soft text-accent font-semibold' : ''}`} onClick={() => setUploadMode('exam')}>
                          考试
                        </button>
                      </div>
                      <div className="flex items-center justify-between gap-2">
                        <div className="text-muted text-[12px]">当前流程状态</div>
                        <span className={`workflow-chip inline-flex items-center px-2 py-0.5 rounded-lg text-[12px] font-semibold border ${
                          activeWorkflowIndicator.tone === 'active'
                            ? 'active text-[#0f766e] border-[#bfe7dc] bg-[#eaf9f4]'
                            : activeWorkflowIndicator.tone === 'success'
                              ? 'success text-[#166534] border-[#bae6c3] bg-[#ecfdf0]'
                              : activeWorkflowIndicator.tone === 'error'
                                ? 'error text-[#991b1b] border-[#fecaca] bg-[#fef2f2]'
                                : 'text-[#5b6473] border-border bg-[#f7f8fa]'
                        }`}>{activeWorkflowIndicator.label}</span>
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        {activeWorkflowIndicator.steps.map((step: WorkflowStepItem) => (
                          <div key={step.key} className={`inline-flex items-center gap-1.5 py-1.5 px-2 rounded-[10px] border text-[12px] ${
                            step.state === 'done'
                              ? 'text-[#0f766e] border-[#bfe7dc] bg-[#eaf9f4]'
                              : step.state === 'active'
                                ? 'text-[#0f766e] border-[#8adac5] bg-[#f1fbf8]'
                                : step.state === 'error'
                                  ? 'text-[#991b1b] border-[#fecaca] bg-[#fef2f2]'
                                  : 'text-[#7b8392] border-[#e8ebf0] bg-[#f9fafb]'
                          }`}>
                            <span className={`w-2 h-2 rounded-full shrink-0 ${
                              step.state === 'done' || step.state === 'active'
                                ? 'bg-[#10a37f]'
                                : step.state === 'error'
                                  ? 'bg-[#dc2626]'
                                  : 'bg-[#cfd6e0]'
                            } ${step.state === 'active' ? 'shadow-[0_0_0_3px_rgba(16,163,127,0.15)]' : ''}`} />
                            <span>{step.label}</span>
                          </div>
                        ))}
                      </div>
                      <div className="text-[12px] leading-[1.45] text-[#3f4551]">
                        {uploadMode === 'assignment'
                          ? formatUploadJobSummary(uploadJobInfo, uploadAssignmentId.trim())
                          : formatExamJobSummary(examJobInfo, examId.trim())}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button type="button" className="ghost" onClick={() => scrollToWorkflowSection('workflow-upload-section')}>
                          定位上传区
                        </button>
                        {uploadMode === 'assignment' ? (
                          <button type="button" className="ghost" onClick={() => scrollToWorkflowSection('workflow-assignment-draft-section')}>
                            定位作业草稿
                          </button>
                        ) : (
                          <button type="button" className="ghost" onClick={() => scrollToWorkflowSection('workflow-exam-draft-section')}>
                            定位考试草稿
                          </button>
                        )}
                        <button type="button" className="ghost" onClick={refreshWorkflowWorkbench}>
                          刷新状态
                        </button>
                      </div>
                    </div>
                    {uploadMode === 'assignment' ? (
                      <div className="border border-border rounded-[14px] bg-white p-[10px] grid gap-2">
                        <div className="text-muted text-[12px]">作业完成情况</div>
                        <div className="text-[12px] leading-[1.45] text-[#3f4551]">{formatProgressSummary(progressData, progressAssignmentId)}</div>
                        <div className="flex flex-wrap gap-2">
                          <button type="button" className="ghost" onClick={() => scrollToWorkflowSection('workflow-progress-section')}>
                            定位完成情况
                          </button>
                          <button type="button" className="ghost" disabled={progressLoading} onClick={() => void fetchAssignmentProgress()}>
                            {progressLoading ? '加载中…' : '刷新完成率'}
                          </button>
                        </div>
                      </div>
                    ) : null}
    </>
  )
}
