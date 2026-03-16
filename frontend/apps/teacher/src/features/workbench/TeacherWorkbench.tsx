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
    progressData,
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
    <aside
      data-testid="teacher-workbench-shell"
      data-workbench-flow="continuous"
      className={`skills-panel border-l border-[color:color-mix(in_oklab,var(--color-border)_86%,white)] bg-[linear-gradient(180deg,color-mix(in_oklab,var(--color-rail)_90%,white)_0%,color-mix(in_oklab,var(--color-surface)_96%,white)_100%)] p-3 shadow-none flex-auto w-full flex-col gap-3 min-h-0 overflow-hidden relative ${skillsOpen ? 'open flex' : 'collapsed hidden'}`}
    >
      <div className="skills-header flex justify-between items-start gap-3 mb-[10px]">
        <div className="grid gap-1">
          <h3 className="m-0">教学编辑台</h3>
          <p className="m-0 text-[12px] text-muted">这里收纳主线摘要与辅助入口。</p>
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
      <section
        className="grid gap-3 rounded-[20px] border border-[color:color-mix(in_oklab,var(--color-border)_76%,white)] bg-[color:color-mix(in_oklab,var(--color-panel)_84%,white)] px-3.5 py-3.5 shadow-none ring-1 ring-inset ring-[color:color-mix(in_oklab,var(--color-surface)_72%,white)]"
        data-testid="teacher-workbench-summary-card"
        data-workbench-tone="summary"
      >
        {workflowTabActive ? (
          <div className="grid gap-2">
            <div className="flex flex-wrap items-center gap-2">
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
            <div
              className="grid gap-1 rounded-[16px] bg-[color:color-mix(in_oklab,var(--color-surface)_72%,white)] px-3 py-2.5 ring-1 ring-inset ring-[color:color-mix(in_oklab,var(--color-border)_68%,white)]"
              data-testid="teacher-workbench-focus-block"
              data-workbench-tier="supporting"
            >
              <div className="text-[11px] font-semibold tracking-[0.12em] text-muted">当前焦点</div>
              <div className="text-[13px] font-semibold text-[color:color-mix(in_oklab,var(--color-ink)_88%,var(--color-accent))]">{focusLabel}</div>
            </div>
          </div>
        ) : (
          <div className="grid gap-3">
            <div className="min-w-0 flex-1 grid gap-2">
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
              <div
                className="grid gap-1 rounded-[16px] bg-[color:color-mix(in_oklab,var(--color-surface)_72%,white)] px-3 py-2.5 ring-1 ring-inset ring-[color:color-mix(in_oklab,var(--color-border)_68%,white)]"
                data-testid="teacher-workbench-focus-block"
                data-workbench-tier="supporting"
              >
                <div className="text-[11px] font-semibold tracking-[0.12em] text-muted">当前焦点</div>
                <div className="text-[14px] font-semibold text-[color:color-mix(in_oklab,var(--color-ink)_88%,var(--color-accent))]">{focusLabel}</div>
              </div>
            </div>
            <button
              type="button"
              className="teacher-rail-cta inline-flex w-full items-center justify-center rounded-[14px] border-none px-[14px] py-[11px] text-white cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed shrink-0"
              onClick={handlePrimaryAction}
            >
              {guidance.primaryActionLabel}
            </button>
          </div>
        )}
      </section>
      <div className="workbench-switch inline-flex border border-[color:color-mix(in_oklab,var(--color-border)_80%,white)] rounded-[12px] overflow-hidden bg-[color:color-mix(in_oklab,var(--color-panel)_94%,white)] self-start flex-none">
        <button type="button" className={`border-0 bg-transparent text-muted text-[12px] py-[6px] px-[12px] cursor-pointer ${workbenchTab === 'skills' ? 'active bg-[color:color-mix(in_oklab,var(--color-accent-soft)_78%,white)] !text-accent font-semibold' : ''}`} onClick={() => setWorkbenchTab('skills')}>
          能力
        </button>
        <button type="button" className={`border-0 border-l border-[color:color-mix(in_oklab,var(--color-border)_80%,white)] bg-transparent text-muted text-[12px] py-[6px] px-[12px] cursor-pointer ${workbenchTab === 'memory' ? 'active bg-[color:color-mix(in_oklab,var(--color-accent-soft)_78%,white)] !text-accent font-semibold' : ''}`} onClick={() => setWorkbenchTab('memory')}>
          自动记忆
        </button>
        <button type="button" className={`border-0 border-l border-[color:color-mix(in_oklab,var(--color-border)_80%,white)] bg-transparent text-muted text-[12px] py-[6px] px-[12px] cursor-pointer ${workbenchTab === 'workflow' ? 'active bg-[color:color-mix(in_oklab,var(--color-accent-soft)_78%,white)] !text-accent font-semibold' : ''}`} onClick={() => setWorkbenchTab('workflow')}>
          工作流
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-hidden border-t border-[color:color-mix(in_oklab,var(--color-border)_72%,white)] pt-3">
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
      </div>
    </aside>
  )
}
