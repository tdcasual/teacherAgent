/**
 * Shared type definitions for the workflow feature.
 *
 * Centralizes types used across WorkflowTab, UploadSection,
 * AssignmentDraftSection, and WorkflowSummaryCard.
 */
import type { FormEvent, KeyboardEvent, Dispatch, SetStateAction } from 'react';
import type {
  AssignmentKind,
  ContentSource,
  UploadJobStatus,
  AssignmentProgress,
  UploadDraft,
  WorkflowIndicator,
} from '../appTypes';

export type { AssignmentKind, ContentSource };

// ── Primitive helpers ──────────────────────────────────────────────────

export type UploadScope = 'public' | 'class' | 'student';

type DifficultyOption = Readonly<{ value: string; label: string }>;

export type AssignmentQuestion = {
  stem?: string;
  answer?: string;
  score?: number;
  difficulty?: string;
  kp?: string;
  kp_id?: string;
  tags?: string[] | string;
  type?: string;
  question_id?: string;
};

// ── Formatter function signatures ──────────────────────────────────────

type FormatUploadJobSummary = (job: UploadJobStatus | null, fallbackId?: string) => string;
export type FormatProgressSummary = (
  data: AssignmentProgress | null,
  assignmentId?: string,
) => string;
type FormatDraftSummary = (draft: UploadDraft | null, jobInfo: UploadJobStatus | null) => string;
type FormatMissingRequirements = (missing?: string[]) => string;
type DifficultyLabel = (value: string | number | undefined) => string;
type NormalizeDifficulty = (value: string | number | undefined) => string;

// ── Utility function signatures ────────────────────────────────────────

type ParseList = (text: string) => string[];
type StopKeyPropagation = (e: KeyboardEvent<HTMLElement>) => void;

// ── Shared prop groups ─────────────────────────────────────────────────

export type UploadSectionProps = {
  uploadCardCollapsed: boolean;
  setUploadCardCollapsed: Dispatch<SetStateAction<boolean>>;

  // Assignment upload fields
  uploadAssignmentId: string;
  setUploadAssignmentId: (v: string) => void;
  uploadDate: string;
  setUploadDate: (v: string) => void;
  uploadDueAt: string;
  setUploadDueAt: (v: string) => void;
  uploadSubjectId: string;
  setUploadSubjectId: (v: string) => void;
  uploadScope: UploadScope;
  setUploadScope: (v: UploadScope) => void;
  uploadClassName: string;
  setUploadClassName: (v: string) => void;
  uploadStudentIds: string;
  setUploadStudentIds: (v: string) => void;
  setUploadFiles: (v: File[]) => void;
  setUploadAnswerFiles: (v: File[]) => void;

  // Job info & status
  uploadJobInfo: UploadJobStatus | null;
  uploadError: string;
  uploadStatus: string;

  // Actions
  handleUploadAssignment: (e: FormEvent) => Promise<void>;

  // Formatters
  formatUploadJobSummary: FormatUploadJobSummary;
};

export type PendingPickerChange = {
  type: 'kind' | 'source';
  value: AssignmentKind | ContentSource;
} | null;

export type AssignmentKindSourcePickerProps = {
  assignmentKind: AssignmentKind;
  contentSource: ContentSource;
  onAssignmentKindChange: (kind: AssignmentKind) => void;
  onContentSourceChange: (source: ContentSource) => void;
};

export type SourceIdentityFieldsProps = {
  assignmentId: string;
  setAssignmentId: (v: string) => void;
  date: string;
  setDate: (v: string) => void;
  dueAt: string;
  setDueAt: (v: string) => void;
  subjectId: string;
  setSubjectId: (v: string) => void;
  className: string;
  setClassName: (v: string) => void;
  studentIds: string;
  setStudentIds: (v: string) => void;
  assignmentIdTestId: string;
};

export type BankPickFormProps = {
  uploading: boolean;
  uploadError: string;
  uploadStatus: string;
  handleFromBank: (input: { kp: string; count: number }) => Promise<void>;
} & SourceIdentityFieldsProps;

export type AiDraftFormProps = {
  assignmentKind: AssignmentKind;
  uploading: boolean;
  uploadError: string;
  uploadStatus: string;
  handleGenerate: (input: {
    kp: string;
    perKp: number;
    topic: string;
    gradeLevel: string;
    seed: string;
  }) => Promise<void>;
} & SourceIdentityFieldsProps;

export type AssignmentDraftSectionProps = {
  uploadDraft: UploadDraft | null;
  uploadJobInfo: UploadJobStatus | null;
  draftPanelCollapsed: boolean;
  setDraftPanelCollapsed: Dispatch<SetStateAction<boolean>>;
  draftActionError: string;
  draftActionStatus: string;
  misconceptionsText: string;
  setMisconceptionsText: (v: string) => void;
  setMisconceptionsDirty: (v: boolean) => void;
  questionShowCount: number;
  setQuestionShowCount: Dispatch<SetStateAction<number>>;

  // Actions
  saveDraft: (draft: UploadDraft) => Promise<void>;
  handleConfirmUpload: () => Promise<void>;
  updateDraftRequirement: (key: string, value: string | string[] | number) => void;
  updateDraftQuestion: (index: number, patch: Record<string, unknown>) => void;

  // Formatters & utils
  formatDraftSummary: FormatDraftSummary;
  formatMissingRequirements: FormatMissingRequirements;
  parseCommaList: ParseList;
  parseLineList: ParseList;
  difficultyLabel: DifficultyLabel;
  normalizeDifficulty: NormalizeDifficulty;
  difficultyOptions: readonly DifficultyOption[];
  stopKeyPropagation: StopKeyPropagation;

  assignmentKind: AssignmentKind;
  completionRequiresSubmission: boolean;
  setCompletionRequiresSubmission: (v: boolean) => void;
  completionRequiresDiscussion: boolean;
  setCompletionRequiresDiscussion: (v: boolean) => void;
  completionAllowPractice: boolean;
  setCompletionAllowPractice: (v: boolean) => void;
};

export type WorkflowSummaryCardProps = {
  activeWorkflowIndicator: WorkflowIndicator;
  uploadJobInfo: UploadJobStatus | null;
  uploadAssignmentId: string;
  progressData: AssignmentProgress | null;
  progressAssignmentId: string;
  progressLoading: boolean;

  // Actions
  scrollToWorkflowSection: (sectionId: string) => void;
  refreshWorkflowWorkbench: () => void;
  fetchAssignmentProgress: (assignmentId?: string) => Promise<void>;

  // Formatters
  formatUploadJobSummary: FormatUploadJobSummary;
  formatProgressSummary: FormatProgressSummary;
};
