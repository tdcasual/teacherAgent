import SkillsTab from './tabs/SkillsTab'
import WorkflowTab from './tabs/WorkflowTab'
import MemoryTab from './tabs/MemoryTab'
import type { TeacherWorkbenchViewModel } from './teacherWorkbenchViewModel'
import { buildTeacherWorkflowGuidance, findActiveWorkflowStep } from './workflowIndicators'

type TeacherWorkbenchProps = {
  viewModel: TeacherWorkbenchViewModel
}

export default function TeacherWorkbench(props: TeacherWorkbenchProps) {
  const { viewModel } = props
  const {
    skillsOpen,
    setSkillsOpen,
    workbenchTab,
    setWorkbenchTab,
    fetchSkills,
    skillsLoading,
    refreshMemoryProposals,
    refreshMemoryInsights,
    refreshStudentMemoryProposals,
    refreshStudentMemoryInsights,
    refreshWorkflowWorkbench,
    proposalLoading,
    studentProposalLoading,
    progressLoading,
    uploading,
    examUploading,
    activeWorkflowIndicator,
    uploadMode,
    uploadJobInfo,
    uploadAssignmentId,
    examJobInfo,
    examId,
    progressData,
    progressAssignmentId,
    formatUploadJobSummary,
    formatExamJobSummary,
    formatProgressSummary,
    scrollToWorkflowSection,
  } = viewModel

  const activeStep = findActiveWorkflowStep(activeWorkflowIndicator)
  const guidance = buildTeacherWorkflowGuidance({
    mode: uploadMode === 'exam' ? 'exam' : 'assignment',
    tone: activeWorkflowIndicator.tone,
    activeStepKey: activeStep?.key,
    hasExecutionTimeline: false,
    hasProgressData: Boolean(progressData),
  })
  const workflowSummary = uploadMode === 'assignment'
    ? (uploadJobInfo || uploadAssignmentId
      ? formatUploadJobSummary(uploadJobInfo, uploadAssignmentId)
      : progressData
        ? formatProgressSummary(progressData, progressAssignmentId || uploadAssignmentId)
        : '从上传区开始今天的作业流程。')
    : (examJobInfo || examId
      ? formatExamJobSummary(examJobInfo, examId)
      : '从上传区开始今天的考试流程。')
  const workflowTabActive = workbenchTab === 'workflow'
  const focusLabel = activeStep?.label || (uploadMode === 'assignment' ? '上传文件' : '上传考试材料')

  const handlePrimaryAction = () => {
    setWorkbenchTab('workflow')
    scrollToWorkflowSection(guidance.primaryActionTargetId)
    if (typeof window !== 'undefined') {
      window.requestAnimationFrame(() => scrollToWorkflowSection(guidance.primaryActionTargetId))
      return
    }
  }

  return (
    <aside className={`skills-panel border-l border-border bg-[#fbfbfc] p-[10px] shadow-none flex-auto w-full flex-col gap-[10px] min-h-0 overflow-hidden relative ${skillsOpen ? 'open flex' : 'collapsed hidden'}`}>
      <div className="skills-header flex justify-between items-start gap-3 mb-[10px]">
        <div className="grid gap-1">
          <h3 className="m-0">教学编辑台</h3>
          <p className="m-0 text-[12px] text-muted">把主动作留在顶部任务条，这里只保留流程摘要与入口。</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            className="ghost"
            onClick={() => {
              if (workbenchTab === 'skills') {
                void fetchSkills()
              } else if (workbenchTab === 'memory') {
                void refreshMemoryProposals()
                void refreshMemoryInsights()
                void refreshStudentMemoryProposals()
                void refreshStudentMemoryInsights()
              } else {
                refreshWorkflowWorkbench()
              }
            }}
            disabled={
              workbenchTab === 'skills'
                ? skillsLoading
                : workbenchTab === 'memory'
                  ? proposalLoading || studentProposalLoading
                  : progressLoading || uploading || examUploading
            }
          >
            刷新
          </button>
          <button className="ghost" onClick={() => setSkillsOpen(false)}>
            收起
          </button>
        </div>
      </div>
      <section className="rounded-[16px] border border-border bg-[color:var(--color-surface-soft)] px-3 py-3 shadow-sm grid gap-2">
        {workflowTabActive ? (
          <div className="grid gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[11px] font-semibold tracking-[0.12em] text-muted">工作流已展开</span>
              <span className="text-[14px] font-semibold text-ink">{activeWorkflowIndicator.label}</span>
              <span data-testid="teacher-workflow-status-chip" className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[12px] font-semibold ${
                activeWorkflowIndicator.tone === 'active'
                  ? 'border-[color:var(--color-accent)] bg-[color:var(--color-accent-soft)] text-[color:var(--color-accent)]'
                  : activeWorkflowIndicator.tone === 'success'
                    ? 'border-[color:var(--color-success)] bg-[color:var(--color-success-soft)] text-[color:var(--color-success)]'
                    : activeWorkflowIndicator.tone === 'error'
                      ? 'border-[color:var(--color-danger)] bg-danger-soft text-danger'
                      : 'border-border bg-surface-soft text-muted'
                }`}>
                {activeStep?.label || '等待开始'}
              </span>
            </div>
            <div className="text-[12px] leading-[1.45] text-muted">当前焦点：{focusLabel}</div>
            <div className="text-[12px] leading-[1.45] text-muted">主动作已经留在顶部任务条，下方继续处理执行细节。</div>
          </div>
        ) : (
          <div className="grid gap-3">
            <div className="min-w-0 flex-1 grid gap-1">
              <div className="text-[11px] font-semibold tracking-[0.12em] text-muted">流程摘要</div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[15px] font-semibold text-ink">{activeWorkflowIndicator.label}</span>
                <span data-testid="teacher-workflow-status-chip" className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[12px] font-semibold ${
                  activeWorkflowIndicator.tone === 'active'
                    ? 'border-[color:var(--color-accent)] bg-[color:var(--color-accent-soft)] text-[color:var(--color-accent)]'
                    : activeWorkflowIndicator.tone === 'success'
                      ? 'border-[color:var(--color-success)] bg-[color:var(--color-success-soft)] text-[color:var(--color-success)]'
                      : activeWorkflowIndicator.tone === 'error'
                        ? 'border-[color:var(--color-danger)] bg-danger-soft text-danger'
                        : 'border-border bg-surface-soft text-muted'
                }`}>
                  {activeStep?.label || '等待开始'}
                </span>
              </div>
              <div className="text-[11px] font-semibold tracking-[0.12em] text-muted">当前焦点</div>
              <div className="text-[14px] font-semibold text-[#334155]">{focusLabel}</div>
              <div className="text-[12px] leading-[1.45] text-muted">{workflowSummary}</div>
            </div>
            <button
              type="button"
              className="inline-flex w-full items-center justify-center rounded-xl border-none bg-accent px-[14px] py-[10px] text-white cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed shrink-0"
              onClick={handlePrimaryAction}
            >
              {guidance.primaryActionLabel}
            </button>
          </div>
        )}
      </section>
      <div className="workbench-switch inline-flex border border-border rounded-[12px] overflow-hidden bg-white self-start flex-none">
        <button type="button" className={`border-0 bg-transparent text-muted text-[12px] py-[6px] px-[12px] cursor-pointer ${workbenchTab === 'skills' ? 'active bg-accent-soft !text-accent font-semibold' : ''}`} onClick={() => setWorkbenchTab('skills')}>
          能力
        </button>
        <button type="button" className={`border-0 border-l border-border bg-transparent text-muted text-[12px] py-[6px] px-[12px] cursor-pointer ${workbenchTab === 'memory' ? 'active bg-accent-soft !text-accent font-semibold' : ''}`} onClick={() => setWorkbenchTab('memory')}>
          自动记忆
        </button>
        <button type="button" className={`border-0 border-l border-border bg-transparent text-muted text-[12px] py-[6px] px-[12px] cursor-pointer ${workbenchTab === 'workflow' ? 'active bg-accent-soft !text-accent font-semibold' : ''}`} onClick={() => setWorkbenchTab('workflow')}>
          工作流
        </button>
      </div>
      {workbenchTab === 'skills' ? (
        <SkillsTab
          apiBase={viewModel.apiBase}
          filteredSkills={viewModel.filteredSkills}
          favorites={viewModel.favorites}
          activeSkillId={viewModel.activeSkillId}
          skillPinned={viewModel.skillPinned}
          skillQuery={viewModel.skillQuery}
          showFavoritesOnly={viewModel.showFavoritesOnly}
          skillsLoading={viewModel.skillsLoading}
          skillsError={viewModel.skillsError}
          fetchSkills={viewModel.fetchSkills}
          chooseSkill={viewModel.chooseSkill}
          toggleFavorite={viewModel.toggleFavorite}
          insertPrompt={viewModel.insertPrompt}
          insertInvocationTokenAtCursor={viewModel.insertInvocationTokenAtCursor}
          stopKeyPropagation={viewModel.stopKeyPropagation}
          setSkillQuery={viewModel.setSkillQuery}
          setShowFavoritesOnly={viewModel.setShowFavoritesOnly}
          setSkillPinned={viewModel.setSkillPinned}
          setComposerWarning={viewModel.setComposerWarning}
        />
      ) : workbenchTab === 'workflow' ? (
        <WorkflowTab {...viewModel} />
      ) : (
        <MemoryTab
          memoryStatusFilter={viewModel.memoryStatusFilter}
          setMemoryStatusFilter={viewModel.setMemoryStatusFilter}
          memoryInsights={viewModel.memoryInsights}
          proposalError={viewModel.proposalError}
          proposalLoading={viewModel.proposalLoading}
          proposals={viewModel.proposals}
          onDeleteProposal={viewModel.onDeleteProposal}
          studentMemoryStatusFilter={viewModel.studentMemoryStatusFilter}
          setStudentMemoryStatusFilter={viewModel.setStudentMemoryStatusFilter}
          studentMemoryStudentFilter={viewModel.studentMemoryStudentFilter}
          setStudentMemoryStudentFilter={viewModel.setStudentMemoryStudentFilter}
          studentMemoryInsights={viewModel.studentMemoryInsights}
          studentProposalError={viewModel.studentProposalError}
          studentProposalLoading={viewModel.studentProposalLoading}
          studentProposals={viewModel.studentProposals}
          onReviewStudentProposal={viewModel.onReviewStudentProposal}
          onDeleteStudentProposal={viewModel.onDeleteStudentProposal}
        />
      )}
    </aside>
  )
}
