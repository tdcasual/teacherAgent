import type { InvocationTriggerType } from './features/chat/invocation'

export type Message = {
  id: string
  role: 'user' | 'assistant'
  content: string
  time: string
}

export type RenderedMessage = Message & { html: string }

export type ChatResponse = {
  reply: string
}

export type ChatJobStatus = {
  job_id: string
  status: 'queued' | 'processing' | 'done' | 'failed' | 'cancelled' | string
  step?: string
  reply?: string
  error?: string
  error_detail?: string
  updated_at?: string
  lane_id?: string
  lane_queue_position?: number
  lane_queue_size?: number
  lane_active?: boolean
}

export type ChatStartResult = {
  ok: boolean
  job_id: string
  status: string
  warnings?: string[]
  lane_id?: string
  lane_queue_position?: number
  lane_queue_size?: number
  lane_active?: boolean
  debounced?: boolean
}

export type PendingChatJob = {
  job_id: string
  request_id: string
  placeholder_id: string
  user_text: string
  session_id: string
  lane_id?: string
  created_at: number
}

export type TeacherHistorySession = {
  session_id: string
  updated_at?: string
  preview?: string
  message_count?: number
  compaction_runs?: number
}

export type SessionGroup<T> = {
  key: string
  label: string
  items: T[]
}

export type TeacherHistorySessionsResponse = {
  ok: boolean
  teacher_id: string
  sessions: TeacherHistorySession[]
  next_cursor?: number | null
  total?: number
}

export type TeacherHistoryMessage = {
  ts?: string
  role?: string
  content?: string
  kind?: string
}

export type TeacherHistorySessionResponse = {
  ok: boolean
  teacher_id: string
  session_id: string
  messages: TeacherHistoryMessage[]
  next_cursor: number
}

export type TeacherMemoryProposal = {
  proposal_id: string
  teacher_id?: string
  target?: string
  title?: string
  content?: string
  source?: string
  status?: string
  created_at?: string
  applied_at?: string
  rejected_at?: string
  reject_reason?: string
  supersedes?: string[]
  superseded_by?: string
}

export type TeacherMemoryProposalListResponse = {
  ok: boolean
  teacher_id: string
  proposals: TeacherMemoryProposal[]
}

export type TeacherMemoryInsightsResponse = {
  ok: boolean
  teacher_id: string
  window_days: number
  summary?: {
    applied_total?: number
    rejected_total?: number
    active_total?: number
    expired_total?: number
    superseded_total?: number
    avg_priority_active?: number
    by_source?: Record<string, number>
    by_target?: Record<string, number>
    rejected_reasons?: Record<string, number>
  }
  retrieval?: {
    search_calls?: number
    search_hit_calls?: number
    search_hit_rate?: number
    search_mode_breakdown?: Record<string, number>
    context_injected?: number
  }
  top_queries?: Array<{
    query: string
    calls: number
    hit_calls: number
    hit_rate: number
  }>
}

export type UploadJobStatus = {
  job_id: string
  status: 'queued' | 'processing' | 'done' | 'failed' | 'confirmed' | 'confirming' | 'created' | 'cancelled'
  progress?: number
  step?: string
  message?: string
  updated_at?: string
  updatedAt?: string
  error?: string
  error_detail?: string
  hints?: string[]
  assignment_id?: string
  question_count?: number
  requirements_missing?: string[]
  warnings?: string[]
  delivery_mode?: string
  questions_preview?: Array<{ id: number; stem: string }>
  draft_saved?: boolean
}

export type UploadDraft = {
  job_id: string
  assignment_id: string
  date: string
  due_at?: string
  scope: 'public' | 'class' | 'student'
  class_name?: string
  student_ids?: string[]
  delivery_mode?: string
  source_files?: string[]
  answer_files?: string[]
  question_count?: number
  draft_version?: string | number
  requirements: UploadDraftRequirements
  requirements_missing?: string[]
  warnings?: string[]
  questions: Array<Record<string, unknown>>
  draft_saved?: boolean
}

export type UploadDraftRequirements = {
  subject?: string
  topic?: string
  grade_level?: string
  class_level?: string
  core_concepts?: string[]
  typical_problem?: string
  misconceptions?: string[]
  duration_minutes?: number
  preferences?: string[]
  extra_constraints?: string
  [k: string]: unknown
}

export type AssignmentProgressStudent = {
  student_id: string
  student_name?: string
  class_name?: string
  complete?: boolean
  overdue?: boolean
  discussion?: { status?: string; pass?: boolean; message_count?: number; last_ts?: string }
  submission?: { attempts?: number; best?: unknown }
}

export type AssignmentProgress = {
  ok: boolean
  assignment_id: string
  date?: string
  scope?: string
  class_name?: string
  due_at?: string
  expected_count?: number
  counts?: { expected?: number; discussion_pass?: number; submitted?: number; completed?: number; overdue?: number }
  students?: AssignmentProgressStudent[]
  updated_at?: string
}

export type ExamScoreSchemaSubjectCandidate = {
  candidate_id: string
  type?: string
  file?: string
  subject_col?: number | null
  subject_header?: string
  score_col?: number | null
  score_header?: string
  rows_considered?: number
  rows_parsed?: number
  rows_invalid?: number
  selected?: boolean
  sample_rows?: Array<{
    student_id?: string
    student_name?: string
    class_name?: string
    raw_value?: string
    score?: number
    status?: string
  }>
}

export type ExamScoreSchemaSubjectCandidateSummary = {
  candidate_id: string
  rows_considered?: number
  rows_parsed?: number
  rows_invalid?: number
  parsed_rate?: number
  source_rank?: number
  files?: string[]
  types?: string[]
  quality_score?: number
}

export type ExamScoreSchemaSubject = {
  target?: string
  question_id?: string
  selected_candidate_id?: string
  suggested_selected_candidate_id?: string
  requested_candidate_id?: string
  selected_candidate_available?: boolean
  recommended_candidate_id?: string
  recommended_candidate_reason?: string
  selection_error?: string
  coverage?: number
  data_rows?: number
  parsed_rows?: number
  unresolved_students?: string[]
  candidate_columns?: ExamScoreSchemaSubjectCandidate[]
  candidate_summaries?: ExamScoreSchemaSubjectCandidateSummary[]
  thresholds?: { coverage?: number; confidence?: number }
}

export type ExamScoreSchema = {
  mode?: string
  confidence?: number
  needs_confirm?: boolean
  confirm?: boolean
  selected_candidate_id?: string
  sources?: Array<Record<string, unknown>>
  subject?: ExamScoreSchemaSubject
}

export type ExamCounts = {
  students?: number
  responses?: number
  questions?: number
  [k: string]: unknown
}

export type ExamCountsScored = {
  students?: number
  responses?: number
  [k: string]: unknown
}

export type ExamTotalsSummary = {
  avg_total?: number
  median_total?: number
  max_total_observed?: number
  [k: string]: unknown
}

export type ExamScoringSummary = {
  status?: string
  responses_total?: number
  responses_scored?: number
  students_total?: number
  students_scored?: number
  default_max_score_qids?: string[]
  [k: string]: unknown
}

export type ExamDraftMeta = {
  date?: string
  class_name?: string
  [k: string]: unknown
}

export type ExamAnswerKeySummary = {
  count?: number
  source?: string
  warnings?: string[]
  [k: string]: unknown
}

export type ExamUploadJobStatus = {
  job_id: string
  status: 'queued' | 'processing' | 'done' | 'failed' | 'confirmed' | 'confirming' | 'cancelled'
  progress?: number
  step?: string
  updated_at?: string
  updatedAt?: string
  error?: string
  error_detail?: string
  hints?: string[]
  exam_id?: string
  counts?: ExamCounts
  counts_scored?: ExamCountsScored
  totals_summary?: ExamTotalsSummary
  scoring?: ExamScoringSummary
  answer_key?: ExamAnswerKeySummary
  warnings?: string[]
  score_schema?: ExamScoreSchema
  needs_confirm?: boolean
}

export type ExamUploadDraft = {
  job_id: string
  exam_id: string
  date?: string
  class_name?: string
  paper_files?: string[]
  score_files?: string[]
  answer_files?: string[]
  counts?: ExamCounts
  counts_scored?: ExamCountsScored
  totals_summary?: ExamTotalsSummary
  scoring?: ExamScoringSummary
  meta: ExamDraftMeta
  questions: Array<Record<string, unknown>>
  score_schema?: ExamScoreSchema
  answer_key?: ExamAnswerKeySummary
  answer_key_text?: string
  answer_text_excerpt?: string
  warnings?: string[]
  needs_confirm?: boolean
  draft_version?: string | number
  draft_saved?: boolean
}

export type Skill = {
  id: string
  title: string
  desc: string
  instructions: string
  prompts: string[]
  examples: string[]
  keywords: string[]
  source_type: 'system' | 'teacher' | 'claude'
}

export type TeacherPersona = {
  persona_id: string
  teacher_id?: string
  name?: string
  summary?: string
  style_rules?: string[]
  few_shot_examples?: string[]
  avatar_url?: string
  intensity_cap?: string
  lifecycle_status?: string
  visibility_mode?: string
  created_at?: string
  updated_at?: string
}

export type TeacherPersonaListResponse = {
  ok: boolean
  teacher_id: string
  personas: TeacherPersona[]
}

export type MentionOption = {
  id: string
  title: string
  desc: string
  type: InvocationTriggerType
}

export type SkillResponse = {
  skills: Array<{
    id: string
    title?: string
    desc?: string
    instructions?: string
    prompts?: string[]
    examples?: string[]
    allowed_roles?: string[]
    source_type?: string
    routing?: { keywords?: string[] }
  }>
}

export type WorkbenchTab = 'skills' | 'memory' | 'workflow'
export type WheelScrollZone = 'chat' | 'session' | 'workbench'

export type WorkflowStepState = 'todo' | 'active' | 'done' | 'error'
export type WorkflowIndicatorTone = 'neutral' | 'active' | 'success' | 'error'
export type WorkflowStepItem = { key: string; label: string; state: WorkflowStepState }
export type WorkflowIndicator = { label: string; tone: WorkflowIndicatorTone; steps: WorkflowStepItem[] }
