import SkillsTab from './tabs/SkillsTab'
import WorkflowTab from './tabs/WorkflowTab'
import MemoryTab from './tabs/MemoryTab'

type WorkbenchTab = 'skills' | 'memory' | 'workflow'

type TeacherWorkbenchProps = {
  skillsOpen: boolean
  setSkillsOpen: any
  workbenchTab: WorkbenchTab
  setWorkbenchTab: any
  activeSkillId: any
  activeWorkflowIndicator: any
  chooseSkill: any
  difficultyLabel: any
  difficultyOptions: readonly any[]
  draftActionError: any
  draftActionStatus: any
  draftError: any
  draftLoading: any
  draftPanelCollapsed: any
  draftSaving: any
  examClassName: any
  examConfirming: any
  examDate: any
  examDraft: any
  examDraftActionError: any
  examDraftActionStatus: any
  examDraftError: any
  examDraftLoading: any
  examDraftPanelCollapsed: any
  examDraftSaving: any
  examId: any
  examJobInfo: any
  examUploadError: any
  examUploadStatus: any
  examUploading: any
  favorites: any[]
  fetchAssignmentProgress: any
  fetchSkills: any
  filteredSkills: any[]
  formatDraftSummary: any
  formatExamDraftSummary: any
  formatExamJobSummary: any
  formatMissingRequirements: any
  formatProgressSummary: any
  formatUploadJobSummary: any
  handleConfirmExamUpload: any
  handleConfirmUpload: any
  handleUploadAssignment: any
  handleUploadExam: any
  insertInvocationTokenAtCursor: any
  insertPrompt: any
  memoryInsights: any
  memoryStatusFilter: any
  misconceptionsText: any
  normalizeDifficulty: any
  parseCommaList: any
  parseLineList: any
  progressAssignmentId: any
  progressData: any
  progressError: any
  progressLoading: any
  progressOnlyIncomplete: any
  progressPanelCollapsed: any
  proposalError: any
  proposalLoading: any
  proposals: any[]
  questionShowCount: any
  refreshMemoryInsights: any
  refreshMemoryProposals: any
  refreshWorkflowWorkbench: any
  saveDraft: any
  saveExamDraft: any
  scrollToWorkflowSection: any
  setComposerWarning: any
  setDraftPanelCollapsed: any
  setExamAnswerFiles: any
  setExamClassName: any
  setExamDate: any
  setExamDraftPanelCollapsed: any
  setExamId: any
  setExamPaperFiles: any
  setExamScoreFiles: any
  setMemoryStatusFilter: any
  setMisconceptionsDirty: any
  setMisconceptionsText: any
  setProgressAssignmentId: any
  setProgressOnlyIncomplete: any
  setProgressPanelCollapsed: any
  setQuestionShowCount: any
  setShowFavoritesOnly: any
  setSkillPinned: any
  setSkillQuery: any
  setUploadAnswerFiles: any
  setUploadAssignmentId: any
  setUploadCardCollapsed: any
  setUploadClassName: any
  setUploadDate: any
  setUploadFiles: any
  setUploadMode: any
  setUploadScope: any
  setUploadStudentIds: any
  showFavoritesOnly: any
  skillPinned: any
  skillQuery: any
  skillsError: any
  skillsLoading: any
  stopKeyPropagation: any
  toggleFavorite: any
  updateDraftQuestion: any
  updateDraftRequirement: any
  updateExamAnswerKeyText: any
  updateExamDraftMeta: any
  updateExamScoreSchemaSelectedCandidate: any
  updateExamQuestionField: any
  uploadAssignmentId: any
  uploadCardCollapsed: any
  uploadClassName: any
  uploadConfirming: any
  uploadDate: any
  uploadDraft: any
  uploadError: any
  uploadJobInfo: any
  uploadMode: any
  uploadScope: any
  uploadStatus: any
  uploadStudentIds: any
  uploading: any
}

export default function TeacherWorkbench(props: TeacherWorkbenchProps) {
  const {
    skillsOpen, setSkillsOpen, workbenchTab, setWorkbenchTab,
    fetchSkills, skillsLoading, refreshMemoryProposals, refreshMemoryInsights,
    refreshWorkflowWorkbench, proposalLoading, progressLoading, uploading, examUploading,
  } = props

  return (
    <aside className={`border-l border-border bg-[#fbfbfc] p-[10px] shadow-none flex-auto w-full flex-col gap-[10px] min-h-0 overflow-hidden relative ${skillsOpen ? 'flex' : 'hidden'}`}>
      <div className="flex justify-between items-center mb-[10px]">
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
              } else {
                refreshWorkflowWorkbench()
              }
            }}
            disabled={
              workbenchTab === 'skills'
                ? skillsLoading
                : workbenchTab === 'memory'
                  ? proposalLoading
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
      <div className="inline-flex border border-border rounded-[12px] overflow-hidden bg-white self-start flex-none">
        <button type="button" className={`border-none bg-transparent text-muted text-[12px] py-[6px] px-[12px] cursor-pointer ${workbenchTab === 'skills' ? 'bg-accent-soft !text-accent font-semibold' : ''}`} onClick={() => setWorkbenchTab('skills')}>
          技能
        </button>
        <button type="button" className={`border-none bg-transparent text-muted text-[12px] py-[6px] px-[12px] cursor-pointer border-l border-border ${workbenchTab === 'memory' ? 'bg-accent-soft !text-accent font-semibold' : ''}`} onClick={() => setWorkbenchTab('memory')}>
          自动记忆
        </button>
        <button type="button" className={`border-none bg-transparent text-muted text-[12px] py-[6px] px-[12px] cursor-pointer border-l border-border ${workbenchTab === 'workflow' ? 'bg-accent-soft !text-accent font-semibold' : ''}`} onClick={() => setWorkbenchTab('workflow')}>
          工作流
        </button>
      </div>
      {workbenchTab === 'skills' ? (
        <SkillsTab
          filteredSkills={props.filteredSkills}
          favorites={props.favorites}
          activeSkillId={props.activeSkillId}
          skillPinned={props.skillPinned}
          skillQuery={props.skillQuery}
          showFavoritesOnly={props.showFavoritesOnly}
          skillsLoading={props.skillsLoading}
          skillsError={props.skillsError}
          fetchSkills={props.fetchSkills}
          chooseSkill={props.chooseSkill}
          toggleFavorite={props.toggleFavorite}
          insertPrompt={props.insertPrompt}
          insertInvocationTokenAtCursor={props.insertInvocationTokenAtCursor}
          stopKeyPropagation={props.stopKeyPropagation}
          setSkillQuery={props.setSkillQuery}
          setShowFavoritesOnly={props.setShowFavoritesOnly}
          setSkillPinned={props.setSkillPinned}
          setComposerWarning={props.setComposerWarning}
        />
      ) : workbenchTab === 'workflow' ? (
        <WorkflowTab {...props} />
      ) : (
        <MemoryTab
          memoryStatusFilter={props.memoryStatusFilter}
          setMemoryStatusFilter={props.setMemoryStatusFilter}
          memoryInsights={props.memoryInsights}
          proposalError={props.proposalError}
          proposalLoading={props.proposalLoading}
          proposals={props.proposals}
        />
      )}
    </aside>
  )
}
