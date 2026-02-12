import type { Dispatch, SetStateAction } from 'react'
import type {
  UploadSectionProps,
  AssignmentDraftSectionProps,
  ExamDraftSectionProps,
  WorkflowSummaryCardProps,
} from '../../../types/workflow'

import WorkflowSummaryCard from '../workflow/WorkflowSummaryCard'
import UploadSection from '../workflow/UploadSection'
import AssignmentProgressSection from '../workflow/AssignmentProgressSection'
import ExamDraftSection from '../workflow/ExamDraftSection'
import AssignmentDraftSection from '../workflow/AssignmentDraftSection'

export type WorkflowTabProps =
  // WorkflowSummaryCard props
  WorkflowSummaryCardProps &
  // UploadSection props
  UploadSectionProps &
  // AssignmentDraftSection props
  AssignmentDraftSectionProps &
  // ExamDraftSection props
  ExamDraftSectionProps & {
    // UploadSection extras (uploading flags)
    uploading: boolean
    examUploading: boolean

    // AssignmentProgressSection props
    progressPanelCollapsed: boolean
    setProgressPanelCollapsed: Dispatch<SetStateAction<boolean>>
    progressAssignmentId: string
    setProgressAssignmentId: (v: string) => void
    progressOnlyIncomplete: boolean
    setProgressOnlyIncomplete: (v: boolean) => void
    progressError: string

    // AssignmentDraftSection extras
    draftLoading: boolean
    draftError: string
    draftSaving: boolean
    uploadConfirming: boolean

    // ExamDraftSection extras
    examDraftLoading: boolean
    examDraftSaving: boolean
    examConfirming: boolean
  }

export default function WorkflowTab(props: WorkflowTabProps) {
  const {
    uploadMode, draftLoading, draftError, uploadDraft,
    examDraftLoading, examDraftError, examDraft,
  } = props

  return (
    <section className="min-h-0 flex-1 overflow-auto grid gap-[10px]" style={{ overscrollBehavior: 'contain' }}>
      <div className="flex justify-between items-center gap-3">
        <strong>作业流程控制</strong>
      </div>
      <WorkflowSummaryCard
        uploadMode={props.uploadMode}
        setUploadMode={props.setUploadMode}
        activeWorkflowIndicator={props.activeWorkflowIndicator}
        formatUploadJobSummary={props.formatUploadJobSummary}
        formatExamJobSummary={props.formatExamJobSummary}
        formatProgressSummary={props.formatProgressSummary}
        uploadJobInfo={props.uploadJobInfo}
        uploadAssignmentId={props.uploadAssignmentId}
        examJobInfo={props.examJobInfo}
        examId={props.examId}
        scrollToWorkflowSection={props.scrollToWorkflowSection}
        refreshWorkflowWorkbench={props.refreshWorkflowWorkbench}
        progressData={props.progressData}
        progressAssignmentId={props.progressAssignmentId}
        progressLoading={props.progressLoading}
        fetchAssignmentProgress={props.fetchAssignmentProgress}
      />
      <UploadSection
        uploadMode={props.uploadMode}
        setUploadMode={props.setUploadMode}
        uploadCardCollapsed={props.uploadCardCollapsed}
        setUploadCardCollapsed={props.setUploadCardCollapsed}
        formatUploadJobSummary={props.formatUploadJobSummary}
        formatExamJobSummary={props.formatExamJobSummary}
        uploadJobInfo={props.uploadJobInfo}
        uploadAssignmentId={props.uploadAssignmentId}
        examJobInfo={props.examJobInfo}
        examId={props.examId}
        handleUploadAssignment={props.handleUploadAssignment}
        handleUploadExam={props.handleUploadExam}
        setUploadAssignmentId={props.setUploadAssignmentId}
        uploadDate={props.uploadDate}
        setUploadDate={props.setUploadDate}
        uploadScope={props.uploadScope}
        setUploadScope={props.setUploadScope}
        uploadClassName={props.uploadClassName}
        setUploadClassName={props.setUploadClassName}
        uploadStudentIds={props.uploadStudentIds}
        setUploadStudentIds={props.setUploadStudentIds}
        setUploadFiles={props.setUploadFiles}
        setUploadAnswerFiles={props.setUploadAnswerFiles}
        uploading={props.uploading}
        uploadError={props.uploadError}
        uploadStatus={props.uploadStatus}
        setExamId={props.setExamId}
        examDate={props.examDate}
        setExamDate={props.setExamDate}
        examClassName={props.examClassName}
        setExamClassName={props.setExamClassName}
        setExamPaperFiles={props.setExamPaperFiles}
        setExamAnswerFiles={props.setExamAnswerFiles}
        setExamScoreFiles={props.setExamScoreFiles}
        examUploading={props.examUploading}
        examUploadError={props.examUploadError}
        examUploadStatus={props.examUploadStatus}
      />
      {uploadMode === 'assignment' && (
        <AssignmentProgressSection
          progressPanelCollapsed={props.progressPanelCollapsed}
          setProgressPanelCollapsed={props.setProgressPanelCollapsed}
          formatProgressSummary={props.formatProgressSummary}
          progressData={props.progressData}
          progressAssignmentId={props.progressAssignmentId}
          setProgressAssignmentId={props.setProgressAssignmentId}
          progressOnlyIncomplete={props.progressOnlyIncomplete}
          setProgressOnlyIncomplete={props.setProgressOnlyIncomplete}
          progressLoading={props.progressLoading}
          fetchAssignmentProgress={props.fetchAssignmentProgress}
          progressError={props.progressError}
        />
      )}

      {uploadMode === 'exam' && examDraftLoading && (
        <section className="mt-3 bg-surface border border-border rounded-[14px] p-[10px] shadow-sm">
          <h3>考试解析结果（审核/修改）</h3>
          <div className="mt-[10px] p-[10px_12px] rounded-xl text-[12px] whitespace-pre-wrap bg-[#e8f7f2] text-[#0f766e]">草稿加载中…</div>
        </section>
      )}
      {uploadMode === 'exam' && examDraftError && (
        <section className="mt-3 bg-surface border border-border rounded-[14px] p-[10px] shadow-sm">
          <h3>考试解析结果（审核/修改）</h3>
          <div className="mt-[10px] p-[10px_12px] rounded-xl text-[12px] whitespace-pre-wrap bg-danger-soft text-danger">{examDraftError}</div>
        </section>
      )}
      {uploadMode === 'exam' && examDraft && (
        <ExamDraftSection
          examDraft={props.examDraft}
          examDraftLoading={props.examDraftLoading}
          examDraftError={props.examDraftError}
          examDraftPanelCollapsed={props.examDraftPanelCollapsed}
          setExamDraftPanelCollapsed={props.setExamDraftPanelCollapsed}
          examDraftSaving={props.examDraftSaving}
          examDraftActionError={props.examDraftActionError}
          examDraftActionStatus={props.examDraftActionStatus}
          examConfirming={props.examConfirming}
          examJobInfo={props.examJobInfo}
          formatExamDraftSummary={props.formatExamDraftSummary}
          saveExamDraft={props.saveExamDraft}
          handleConfirmExamUpload={props.handleConfirmExamUpload}
          updateExamDraftMeta={props.updateExamDraftMeta}
          updateExamQuestionField={props.updateExamQuestionField}
          updateExamAnswerKeyText={props.updateExamAnswerKeyText}
          updateExamScoreSchemaSelectedCandidate={props.updateExamScoreSchemaSelectedCandidate}
          stopKeyPropagation={props.stopKeyPropagation}
        />
      )}

      {uploadMode === 'assignment' && draftLoading && (
        <section className="mt-3 bg-surface border border-border rounded-[14px] p-[10px] shadow-sm">
          <h3>解析结果（审核/修改）</h3>
          <div className="mt-[10px] p-[10px_12px] rounded-xl text-[12px] whitespace-pre-wrap bg-[#e8f7f2] text-[#0f766e]">草稿加载中…</div>
        </section>
      )}
      {uploadMode === 'assignment' && draftError && (
        <section className="mt-3 bg-surface border border-border rounded-[14px] p-[10px] shadow-sm">
          <h3>解析结果（审核/修改）</h3>
          <div className="mt-[10px] p-[10px_12px] rounded-xl text-[12px] whitespace-pre-wrap bg-danger-soft text-danger">{draftError}</div>
        </section>
      )}
      {uploadMode === 'assignment' && uploadDraft && (
        <AssignmentDraftSection
          uploadDraft={props.uploadDraft}
          uploadJobInfo={props.uploadJobInfo}
          draftPanelCollapsed={props.draftPanelCollapsed}
          setDraftPanelCollapsed={props.setDraftPanelCollapsed}
          draftActionError={props.draftActionError}
          draftActionStatus={props.draftActionStatus}
          draftSaving={props.draftSaving}
          saveDraft={props.saveDraft}
          handleConfirmUpload={props.handleConfirmUpload}
          uploadConfirming={props.uploadConfirming}
          formatDraftSummary={props.formatDraftSummary}
          formatMissingRequirements={props.formatMissingRequirements}
          updateDraftRequirement={props.updateDraftRequirement}
          updateDraftQuestion={props.updateDraftQuestion}
          misconceptionsText={props.misconceptionsText}
          setMisconceptionsText={props.setMisconceptionsText}
          setMisconceptionsDirty={props.setMisconceptionsDirty}
          parseCommaList={props.parseCommaList}
          parseLineList={props.parseLineList}
          difficultyLabel={props.difficultyLabel}
          difficultyOptions={props.difficultyOptions}
          normalizeDifficulty={props.normalizeDifficulty}
          questionShowCount={props.questionShowCount}
          setQuestionShowCount={props.setQuestionShowCount}
          stopKeyPropagation={props.stopKeyPropagation}
        />
      )}
    </section>
  )
}
