import type { Dispatch, SetStateAction } from 'react';
import type {
  UploadSectionProps,
  AssignmentDraftSectionProps,
  WorkflowSummaryCardProps,
} from '../../../types/workflow';
import type { ExecutionTimelineEntry } from '../../../appTypes';

import WorkflowSummaryCard from '../workflow/WorkflowSummaryCard';
import UploadSection from '../workflow/UploadSection';
import AssignmentProgressSection from '../workflow/AssignmentProgressSection';
import AssignmentDraftSection from '../workflow/AssignmentDraftSection';
import WorkflowTimeline from '../workflow/WorkflowTimeline';
import { findActiveWorkflowStep } from '../workflowIndicators';

export type WorkflowTabProps = WorkflowSummaryCardProps &
  UploadSectionProps &
  AssignmentDraftSectionProps & {
    uploading: boolean;
    progressPanelCollapsed: boolean;
    setProgressPanelCollapsed: Dispatch<SetStateAction<boolean>>;
    progressAssignmentId: string;
    setProgressAssignmentId: (v: string) => void;
    progressOnlyIncomplete: boolean;
    setProgressOnlyIncomplete: (v: boolean) => void;
    progressError: string;
    archiveAssignment?: (assignmentId?: string) => Promise<void>;
    unarchiveAssignment?: (assignmentId?: string) => Promise<void>;
    saveStudentGrade?: (
      studentId: string,
      payload: {
        override_score?: number | null;
        comment?: string;
        adopted_coach_excerpts?: Array<{ text: string }>;
      },
    ) => Promise<void>;
    draftLoading: boolean;
    draftError: string;
    draftSaving: boolean;
    uploadConfirming: boolean;
    executionTimeline: ExecutionTimelineEntry[];
  };

export default function WorkflowTab(props: WorkflowTabProps) {
  const { draftLoading, draftError, uploadDraft } = props;
  const activeStep = findActiveWorkflowStep(props.activeWorkflowIndicator);
  const focusLabel = activeStep?.label || '上传文件';

  return (
    <section
      className="min-h-0 flex-1 overflow-auto grid gap-[10px]"
      style={{ overscrollBehavior: 'contain' }}
    >
      <div className="grid gap-1 pb-1 border-b border-[color:color-mix(in_oklab,var(--color-border)_72%,var(--color-surface))]">
        <strong>工作流编辑</strong>
        <div className="text-[12px] text-muted">先完成必做动作，再展开补充参考。</div>
      </div>
      <WorkflowSummaryCard
        activeWorkflowIndicator={props.activeWorkflowIndicator}
        formatUploadJobSummary={props.formatUploadJobSummary}
        formatProgressSummary={props.formatProgressSummary}
        uploadJobInfo={props.uploadJobInfo}
        uploadAssignmentId={props.uploadAssignmentId}
        scrollToWorkflowSection={props.scrollToWorkflowSection}
        refreshWorkflowWorkbench={props.refreshWorkflowWorkbench}
        progressData={props.progressData}
        progressAssignmentId={props.progressAssignmentId}
        progressLoading={props.progressLoading}
        fetchAssignmentProgress={props.fetchAssignmentProgress}
      />
      <section
        className="grid gap-3 rounded-[20px] border border-[color:color-mix(in_oklab,var(--color-border)_76%,var(--color-surface))] bg-[color:color-mix(in_oklab,var(--color-panel)_84%,var(--color-surface))] p-[12px] shadow-none ring-1 ring-inset ring-[color:color-mix(in_oklab,var(--color-surface)_74%,var(--color-surface))]"
        data-testid="teacher-workflow-primary-stage"
        data-workflow-tier="primary"
      >
        <div className="grid gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-semibold tracking-[0.12em] text-muted">主线流程</span>
            <span className="inline-flex items-center rounded-full border border-[color:var(--color-accent)] bg-[color:var(--color-accent-soft)] px-2 py-0.5 text-[11px] font-semibold text-[color:var(--color-accent)]">
              必做
            </span>
          </div>
          <strong>必做动作</strong>
          <div className="text-[12px] text-muted">按下面的主线动作继续处理。</div>
          <div className="text-[12px] text-muted">当前焦点：{focusLabel}</div>
        </div>
        <UploadSection
          uploadCardCollapsed={props.uploadCardCollapsed}
          setUploadCardCollapsed={props.setUploadCardCollapsed}
          formatUploadJobSummary={props.formatUploadJobSummary}
          uploadJobInfo={props.uploadJobInfo}
          uploadAssignmentId={props.uploadAssignmentId}
          handleUploadAssignment={props.handleUploadAssignment}
          setUploadAssignmentId={props.setUploadAssignmentId}
          uploadDate={props.uploadDate}
          setUploadDate={props.setUploadDate}
          uploadDueAt={props.uploadDueAt}
          setUploadDueAt={props.setUploadDueAt}
          uploadSubjectId={props.uploadSubjectId}
          setUploadSubjectId={props.setUploadSubjectId}
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
        />
        {draftLoading && (
          <section className="mt-3 bg-surface border border-border rounded-[14px] p-[10px] shadow-sm">
            <h3>解析结果（审核/修改）</h3>
            <div className="mt-[10px] p-[10px_12px] rounded-xl text-[12px] whitespace-pre-wrap bg-success-soft text-success">
              草稿加载中…
            </div>
          </section>
        )}
        {draftError && (
          <section className="mt-3 bg-surface border border-border rounded-[14px] p-[10px] shadow-sm">
            <h3>解析结果（审核/修改）</h3>
            <div className="mt-[10px] p-[10px_12px] rounded-xl text-[12px] whitespace-pre-wrap bg-danger-soft text-danger">
              {draftError}
            </div>
          </section>
        )}
        {uploadDraft && (
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
      <section
        className="grid gap-3 border-t border-[color:color-mix(in_oklab,var(--color-border)_72%,var(--color-surface))] pt-3"
        data-testid="teacher-workflow-secondary-stage"
        data-workflow-tier="supporting"
      >
        <div className="grid gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-semibold tracking-[0.12em] text-muted">补充视图</span>
            <span className="inline-flex items-center rounded-full border border-border bg-white px-2 py-0.5 text-[11px] font-semibold text-muted">
              按需查看
            </span>
          </div>
          <strong>补充参考</strong>
          <div className="text-[12px] text-muted">
            完成情况与执行记录放在这里，主线处理完成后再看。
          </div>
        </div>
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
          archiveAssignment={props.archiveAssignment}
          unarchiveAssignment={props.unarchiveAssignment}
          saveStudentGrade={props.saveStudentGrade}
        />
        <WorkflowTimeline entries={props.executionTimeline} />
      </section>
    </section>
  );
}
