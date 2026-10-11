import type { Dispatch, SetStateAction } from 'react';
import type {
  UploadSectionProps,
  AssignmentDraftSectionProps,
  PendingPickerChange,
  WorkflowSummaryCardProps,
} from '../../../types/workflow';
import type { AssignmentKind, ContentSource, ExecutionTimelineEntry } from '../../../appTypes';
import { ConfirmDialog } from '../../../../../shared/dialog';

import WorkflowSummaryCard from '../workflow/WorkflowSummaryCard';
import UploadSection from '../workflow/UploadSection';
import AssignmentProgressSection from '../workflow/AssignmentProgressSection';
import AssignmentDraftSection from '../workflow/AssignmentDraftSection';
import AssignmentKindSourcePicker from '../workflow/AssignmentKindSourcePicker';
import BankPickForm from '../workflow/BankPickForm';
import AiDraftForm from '../workflow/AiDraftForm';
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
    assignmentKind: AssignmentKind;
    contentSource: ContentSource;
    requestAssignmentKindChange: (kind: AssignmentKind) => void;
    requestContentSourceChange: (source: ContentSource) => void;
    pendingPickerChange: PendingPickerChange;
    confirmPendingPickerChange: () => void;
    cancelPendingPickerChange: () => void;
    handleFromBank: (input: { kp: string; count: number }) => Promise<void>;
    handleGenerate: (input: {
      kp: string;
      perKp: number;
      topic: string;
      gradeLevel: string;
      seed: string;
    }) => Promise<void>;
  };

export default function WorkflowTab(props: WorkflowTabProps) {
  const { draftLoading, draftError, uploadDraft } = props;
  const activeStep = findActiveWorkflowStep(props.activeWorkflowIndicator);
  const focusLabel = activeStep?.label || '上传文件';
  const sourceBusy = props.uploading || Boolean(props.pendingPickerChange);

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
        contentSource={props.contentSource}
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
        <AssignmentKindSourcePicker
          assignmentKind={props.assignmentKind}
          contentSource={props.contentSource}
          onAssignmentKindChange={props.requestAssignmentKindChange}
          onContentSourceChange={props.requestContentSourceChange}
        />
        {props.contentSource === 'upload' ? (
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
            uploading={sourceBusy}
            uploadError={props.uploadError}
            uploadStatus={props.uploadStatus}
          />
        ) : null}
        {props.contentSource === 'bank' && props.assignmentKind === 'problem_set' ? (
          <BankPickForm
            assignmentId={props.uploadAssignmentId}
            setAssignmentId={props.setUploadAssignmentId}
            date={props.uploadDate}
            setDate={props.setUploadDate}
            dueAt={props.uploadDueAt}
            setDueAt={props.setUploadDueAt}
            subjectId={props.uploadSubjectId}
            setSubjectId={props.setUploadSubjectId}
            className={props.uploadClassName}
            setClassName={props.setUploadClassName}
            studentIds={props.uploadStudentIds}
            setStudentIds={props.setUploadStudentIds}
            uploading={sourceBusy}
            uploadError={props.uploadError}
            uploadStatus={props.uploadStatus}
            handleFromBank={props.handleFromBank}
          />
        ) : null}
        {props.contentSource === 'ai' ? (
          <AiDraftForm
            assignmentKind={props.assignmentKind}
            assignmentId={props.uploadAssignmentId}
            setAssignmentId={props.setUploadAssignmentId}
            date={props.uploadDate}
            setDate={props.setUploadDate}
            dueAt={props.uploadDueAt}
            setDueAt={props.setUploadDueAt}
            subjectId={props.uploadSubjectId}
            setSubjectId={props.setUploadSubjectId}
            className={props.uploadClassName}
            setClassName={props.setUploadClassName}
            studentIds={props.uploadStudentIds}
            setStudentIds={props.setUploadStudentIds}
            uploading={sourceBusy}
            uploadError={props.uploadError}
            uploadStatus={props.uploadStatus}
            handleGenerate={props.handleGenerate}
          />
        ) : null}
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
            assignmentKind={props.assignmentKind}
            completionRequiresSubmission={props.completionRequiresSubmission}
            setCompletionRequiresSubmission={props.setCompletionRequiresSubmission}
            completionRequiresDiscussion={props.completionRequiresDiscussion}
            setCompletionRequiresDiscussion={props.setCompletionRequiresDiscussion}
            completionAllowPractice={props.completionAllowPractice}
            setCompletionAllowPractice={props.setCompletionAllowPractice}
          />
        )}
      </section>
      <ConfirmDialog
        open={Boolean(props.pendingPickerChange)}
        title={props.pendingPickerChange?.type === 'kind' ? '更换作业类型？' : '更换草稿来源？'}
        description="当前草稿将被清空，以免把已有稿改成另一种作业。"
        confirmText="清空并更换"
        confirmTone="danger"
        onConfirm={props.confirmPendingPickerChange}
        onCancel={props.cancelPendingPickerChange}
      />
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
          assignmentKind={props.assignmentKind}
        />
        <WorkflowTimeline entries={props.executionTimeline} />
      </section>
    </section>
  );
}
