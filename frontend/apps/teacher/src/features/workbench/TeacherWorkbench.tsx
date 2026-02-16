import SkillsTab from './tabs/SkillsTab'
import WorkflowTab from './tabs/WorkflowTab'
import MemoryTab from './tabs/MemoryTab'
import type { TeacherWorkbenchViewModel } from './teacherWorkbenchViewModel'

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
  } = viewModel

  return (
    <aside className={`skills-panel border-l border-border bg-[#fbfbfc] p-[10px] shadow-none flex-auto w-full flex-col gap-[10px] min-h-0 overflow-hidden relative ${skillsOpen ? 'open flex' : 'collapsed hidden'}`}>
      <div className="skills-header flex justify-between items-center mb-[10px]">
        <h3 className="m-0">工作台</h3>
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
      <div className="workbench-switch inline-flex border border-border rounded-[12px] overflow-hidden bg-white self-start flex-none">
        <button type="button" className={`border-0 bg-transparent text-muted text-[12px] py-[6px] px-[12px] cursor-pointer ${workbenchTab === 'skills' ? 'active bg-accent-soft !text-accent font-semibold' : ''}`} onClick={() => setWorkbenchTab('skills')}>
          技能
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
