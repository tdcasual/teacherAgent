import type { Dispatch, SetStateAction } from 'react'
import type {
  UploadSectionProps,
  AssignmentDraftSectionProps,
  ExamDraftSectionProps,
  WorkflowSummaryCardProps,
  AnalysisReportSectionProps,
  VideoHomeworkAnalysisSectionProps,
} from '../../../types/workflow'
import type { ExecutionTimelineEntry } from '../../../appTypes'

import WorkflowSummaryCard from '../workflow/WorkflowSummaryCard'
import UploadSection from '../workflow/UploadSection'
import AssignmentProgressSection from '../workflow/AssignmentProgressSection'
import ExamDraftSection from '../workflow/ExamDraftSection'
import AssignmentDraftSection from '../workflow/AssignmentDraftSection'
import AnalysisReportSection from '../workflow/AnalysisReportSection'
import VideoHomeworkAnalysisSection from '../workflow/VideoHomeworkAnalysisSection'
import WorkflowTimeline from '../workflow/WorkflowTimeline'
import { buildTeacherWorkflowGuidance, findActiveWorkflowStep } from '../workflowIndicators'

export type WorkflowTabProps =
  WorkflowSummaryCardProps &
  UploadSectionProps &
  AssignmentDraftSectionProps &
  ExamDraftSectionProps &
  AnalysisReportSectionProps &
  VideoHomeworkAnalysisSectionProps & {
    uploading: boolean
    examUploading: boolean
    progressPanelCollapsed: boolean
    setProgressPanelCollapsed: Dispatch<SetStateAction<boolean>>
    progressAssignmentId: string
    setProgressAssignmentId: (v: string) => void
    progressOnlyIncomplete: boolean
    setProgressOnlyIncomplete: (v: boolean) => void
    progressError: string
    draftLoading: boolean
    draftError: string
    draftSaving: boolean
    uploadConfirming: boolean
    examDraftLoading: boolean
    examDraftSaving: boolean
    examConfirming: boolean
    executionTimeline: ExecutionTimelineEntry[]
  }

export default function WorkflowTab(props: WorkflowTabProps) {
  const {
    uploadMode, draftLoading, draftError, uploadDraft,
    examDraftLoading, examDraftError, examDraft,
  } = props
  const isAssignmentMode = uploadMode === 'assignment'
  const activeStep = findActiveWorkflowStep(props.activeWorkflowIndicator)
  const guidance = buildTeacherWorkflowGuidance({
    mode: isAssignmentMode ? 'assignment' : 'exam',
    tone: props.activeWorkflowIndicator.tone,
    activeStepKey: activeStep?.key,
    hasExecutionTimeline: props.executionTimeline.length > 0,
    hasProgressData: Boolean(props.progressData),
  })

  return (
    <section className="min-h-0 flex-1 overflow-auto grid gap-[10px]" style={{ overscrollBehavior: 'contain' }}>
      <div className="grid gap-1">
        <strong>工作流编辑</strong>
        <div className="text-[12px] text-muted">先完成必做动作，再展开补充参考。</div>
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
      <section className="grid gap-3 rounded-[16px] border border-border bg-white p-[12px] shadow-sm">
        <div className="grid gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-semibold tracking-[0.12em] text-muted">主线流程</span>
            <span className="inline-flex items-center rounded-full border border-[color:var(--color-accent)] bg-[color:var(--color-accent-soft)] px-2 py-0.5 text-[11px] font-semibold text-[color:var(--color-accent)]">
              必做
            </span>
          </div>
          <strong>必做动作</strong>
          <div className="text-[12px] text-muted">按主线步骤往下处理，避免在次要信息里来回切换。</div>
          <div className="text-[13px] font-semibold text-[#334155]">{guidance.nextStepLabel}</div>
        </div>
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
      <section className="grid gap-3 rounded-[16px] border border-dashed border-border bg-[color:var(--color-surface-soft)] p-[12px] shadow-sm">
        <div className="grid gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-semibold tracking-[0.12em] text-muted">补充视图</span>
            <span className="inline-flex items-center rounded-full border border-border bg-white px-2 py-0.5 text-[11px] font-semibold text-muted">
              按需查看
            </span>
          </div>
          <strong>补充参考</strong>
          <div className="text-[12px] text-muted">
            {isAssignmentMode
              ? '完成情况、执行记录与分析结果放在这里，主线处理完成后再看。'
              : '执行记录与分析结果会补充在这里。'}
          </div>
        </div>
        {isAssignmentMode && (
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
        <WorkflowTimeline entries={props.executionTimeline} />
        <AnalysisReportSection
          analysisFeatureEnabled={props.analysisFeatureEnabled}
          analysisFeatureShadowMode={props.analysisFeatureShadowMode}
          analysisReportsLoading={props.analysisReportsLoading}
          analysisReportsError={props.analysisReportsError}
          analysisReports={props.analysisReports}
          selectedAnalysisReportId={props.selectedAnalysisReportId}
          selectedAnalysisReport={props.selectedAnalysisReport}
          analysisReviewQueue={props.analysisReviewQueue}
          analysisReportsSummary={props.analysisReportsSummary}
          analysisReviewSummary={props.analysisReviewSummary}
          analysisOpsSnapshot={props.analysisOpsSnapshot}
          analysisDomainFilter={props.analysisDomainFilter}
          analysisStatusFilter={props.analysisStatusFilter}
          analysisStrategyFilter={props.analysisStrategyFilter}
          analysisTargetTypeFilter={props.analysisTargetTypeFilter}
          setAnalysisDomainFilter={props.setAnalysisDomainFilter}
          setAnalysisStatusFilter={props.setAnalysisStatusFilter}
          setAnalysisStrategyFilter={props.setAnalysisStrategyFilter}
          setAnalysisTargetTypeFilter={props.setAnalysisTargetTypeFilter}
          refreshAnalysisReports={props.refreshAnalysisReports}
          selectAnalysisReport={props.selectAnalysisReport}
          rerunAnalysisReport={props.rerunAnalysisReport}
          rerunAnalysisReportsBulk={props.rerunAnalysisReportsBulk}
        />
        <VideoHomeworkAnalysisSection
          videoHomeworkFeatureEnabled={props.videoHomeworkFeatureEnabled}
          analysisReports={props.analysisReports}
          selectedAnalysisReport={props.selectedAnalysisReport}
        />
      </section>
    </section>
  )
}
