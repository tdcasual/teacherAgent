import type { InvocationTriggerType } from './features/chat/invocation';

export type Message = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  time: string;
};

export type RenderedMessage = Message & { html: string };

export type ChatJobStatus = {
  job_id: string;
  status: 'queued' | 'processing' | 'done' | 'failed' | 'cancelled' | string;
  step?: string;
  reply?: string;
  error?: string;
  error_detail?: string;
  updated_at?: string;
  lane_id?: string;
  lane_queue_position?: number;
  lane_queue_size?: number;
  lane_active?: boolean;
  skill_id_requested?: string;
  skill_id_effective?: string;
  skill_reason?: string;
  skill_confidence?: number;
  skill_candidates?: Array<{
    skill_id: string;
    score?: number;
    hits?: string[];
  }>;
  execution_timeline?: ExecutionTimelineEntry[];
};

export type ChatStartResult = {
  ok: boolean;
  job_id: string;
  status: string;
  warnings?: string[];
  lane_id?: string;
  lane_queue_position?: number;
  lane_queue_size?: number;
  lane_active?: boolean;
  debounced?: boolean;
};

export type PendingChatJob = {
  job_id: string;
  request_id: string;
  placeholder_id: string;
  user_text: string;
  session_id: string;
  lane_id?: string;
  created_at: number;
};

export type PendingToolRun = {
  key: string;
  name: string;
  status: 'running' | 'ok' | 'failed';
  durationMs?: number;
  error?: string;
};

export type ExecutionTimelineEntry = {
  type: string;
  summary: string;
  ts?: string;
  meta?: Record<string, unknown>;
};

export type TeacherHistorySession = {
  session_id: string;
  updated_at?: string;
  preview?: string;
  message_count?: number;
  compaction_runs?: number;
};

export type SessionGroup<T> = {
  key: string;
  label: string;
  items: T[];
};

export type TeacherHistorySessionsResponse = {
  ok: boolean;
  teacher_id: string;
  sessions: TeacherHistorySession[];
  next_cursor?: number | null;
  total?: number;
};

type TeacherHistoryMessage = {
  ts?: string;
  role?: string;
  content?: string;
  kind?: string;
};

export type TeacherHistorySessionResponse = {
  ok: boolean;
  teacher_id: string;
  session_id: string;
  messages: TeacherHistoryMessage[];
  next_cursor: number;
};

export type TeacherMemoryProposal = {
  proposal_id: string;
  teacher_id?: string;
  target?: string;
  title?: string;
  content?: string;
  source?: string;
  status?: string;
  created_at?: string;
  applied_at?: string;
  rejected_at?: string;
  reject_reason?: string;
  supersedes?: string[];
  superseded_by?: string;
};

export type TeacherMemoryProposalListResponse = {
  ok: boolean;
  teacher_id: string;
  proposals: TeacherMemoryProposal[];
};

export type TeacherMemoryInsightsResponse = {
  ok: boolean;
  teacher_id: string;
  window_days: number;
  summary?: {
    applied_total?: number;
    rejected_total?: number;
    active_total?: number;
    expired_total?: number;
    superseded_total?: number;
    avg_priority_active?: number;
    by_source?: Record<string, number>;
    by_target?: Record<string, number>;
    rejected_reasons?: Record<string, number>;
  };
  retrieval?: {
    search_calls?: number;
    search_hit_calls?: number;
    search_hit_rate?: number;
    search_mode_breakdown?: Record<string, number>;
    context_injected?: number;
  };
  top_queries?: Array<{
    query: string;
    calls: number;
    hit_calls: number;
    hit_rate: number;
  }>;
};

export type StudentMemoryProposal = {
  proposal_id: string;
  teacher_id?: string;
  student_id?: string;
  memory_type?: string;
  content?: string;
  source?: string;
  status?: string;
  created_at?: string;
  reviewed_at?: string;
  reviewed_by?: string;
  deleted_at?: string;
  deleted_from_status?: string;
  evidence_refs?: string[];
  risk_flags?: string[];
};

export type StudentMemoryProposalListResponse = {
  ok: boolean;
  teacher_id: string;
  student_id?: string | null;
  proposals: StudentMemoryProposal[];
};

export type StudentMemoryInsightsResponse = {
  ok: boolean;
  teacher_id: string;
  student_id?: string | null;
  days: number;
  total: number;
  status_counts?: Record<string, number>;
  type_counts?: Record<string, number>;
};

export type UploadJobStatus = {
  job_id: string;
  status:
    | 'queued'
    | 'processing'
    | 'done'
    | 'failed'
    | 'confirmed'
    | 'confirming'
    | 'created'
    | 'cancelled';
  progress?: number;
  step?: string;
  message?: string;
  updated_at?: string;
  updatedAt?: string;
  error?: string;
  error_detail?: string;
  hints?: string[];
  assignment_id?: string;
  question_count?: number;
  requirements_missing?: string[];
  warnings?: string[];
  delivery_mode?: string;
  questions_preview?: Array<{ id: number; stem: string }>;
  draft_saved?: boolean;
};

export type UploadDraft = {
  job_id: string;
  assignment_id: string;
  date: string;
  due_at?: string;
  scope: 'public' | 'class' | 'student';
  class_name?: string;
  student_ids?: string[];
  delivery_mode?: string;
  source_files?: string[];
  answer_files?: string[];
  question_count?: number;
  draft_version?: string | number;
  requirements: UploadDraftRequirements;
  requirements_missing?: string[];
  warnings?: string[];
  questions: Array<Record<string, unknown>>;
  draft_saved?: boolean;
};

type UploadDraftRequirements = {
  subject?: string;
  topic?: string;
  grade_level?: string;
  class_level?: string;
  core_concepts?: string[];
  typical_problem?: string;
  misconceptions?: string[];
  duration_minutes?: number;
  preferences?: string[];
  extra_constraints?: string;
  [k: string]: unknown;
};

export type AssignmentProgressStudent = {
  student_id: string;
  student_name?: string;
  class_name?: string;
  complete?: boolean;
  overdue?: boolean;
  official_score?: number | null;
  discussion?: { status?: string; pass?: boolean; message_count?: number; last_ts?: string };
  submission?: { attempts?: number; best?: unknown };
  result?: {
    attempts?: number;
    official_score?: number | null;
    overdue?: boolean;
    submitted?: boolean;
  };
  process?: {
    status?: string;
    stuck_points?: Array<{ summary?: string }>;
    has_memory_proposal?: boolean;
  };
  teacher_grade?: {
    comment?: string;
    override_score_earned?: number | null;
    adopted_coach_excerpts?: Array<{ text?: string }>;
  };
  process_archive_status?: string;
  process_archive?: {
    status?: string;
    stuck_points?: Array<{ summary?: string }>;
    process_archive_id?: string;
  };
  has_memory_proposal?: boolean;
};

export type AssignmentProgress = {
  ok: boolean;
  assignment_id: string;
  date?: string;
  scope?: string;
  class_name?: string;
  visibility_status?: string;
  archived_at?: string | null;
  due_at?: string;
  expected_count?: number;
  counts?: {
    expected?: number;
    discussion_pass?: number;
    submitted?: number;
    completed?: number;
    overdue?: number;
  };
  students?: AssignmentProgressStudent[];
  updated_at?: string;
};

export type Skill = {
  id: string;
  title: string;
  desc: string;
  instructions: string;
  prompts: string[];
  examples: string[];
  keywords: string[];
  source_type: 'system' | 'teacher' | 'claude';
};

export type MentionOption = {
  id: string;
  title: string;
  desc: string;
  type: InvocationTriggerType;
};

export type SkillResponse = {
  skills: Array<{
    id: string;
    title?: string;
    desc?: string;
    instructions?: string;
    prompts?: string[];
    examples?: string[];
    allowed_roles?: string[];
    source_type?: string;
    routing?: { keywords?: string[] };
  }>;
};

export type WorkbenchTab = 'skills' | 'memory' | 'workflow';
export type WheelScrollZone = 'chat' | 'session' | 'workbench';

export type WorkflowStepState = 'todo' | 'active' | 'done' | 'error';
export type WorkflowIndicatorTone = 'neutral' | 'active' | 'success' | 'error';
export type WorkflowStepItem = { key: string; label: string; state: WorkflowStepState };
export type WorkflowIndicator = {
  label: string;
  tone: WorkflowIndicatorTone;
  steps: WorkflowStepItem[];
};
