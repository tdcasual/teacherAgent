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
  error?: string
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
  requirements: Record<string, any>
  requirements_missing?: string[]
  warnings?: string[]
  questions: Array<Record<string, any>>
  draft_saved?: boolean
}

export type AssignmentProgressStudent = {
  student_id: string
  student_name?: string
  class_name?: string
  complete?: boolean
  overdue?: boolean
  discussion?: { status?: string; pass?: boolean; message_count?: number; last_ts?: string }
  submission?: { attempts?: number; best?: any }
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

export type ExamScoreSchemaSubject = {
  target?: string
  question_id?: string
  selected_candidate_id?: string
  requested_candidate_id?: string
  selected_candidate_available?: boolean
  coverage?: number
  data_rows?: number
  parsed_rows?: number
  unresolved_students?: string[]
  candidate_columns?: ExamScoreSchemaSubjectCandidate[]
  thresholds?: { coverage?: number; confidence?: number }
}

export type ExamScoreSchema = {
  mode?: string
  confidence?: number
  needs_confirm?: boolean
  confirm?: boolean
  selected_candidate_id?: string
  sources?: Array<Record<string, any>>
  subject?: ExamScoreSchemaSubject
}

export type ExamUploadJobStatus = {
  job_id: string
  status: 'queued' | 'processing' | 'done' | 'failed' | 'confirmed' | 'confirming' | 'cancelled'
  progress?: number
  step?: string
  error?: string
  error_detail?: string
  exam_id?: string
  counts?: { students?: number; responses?: number; questions?: number }
  counts_scored?: { students?: number; responses?: number }
  totals_summary?: Record<string, any>
  scoring?: {
    status?: string
    responses_total?: number
    responses_scored?: number
    students_total?: number
    students_scored?: number
    default_max_score_qids?: string[]
  }
  answer_key?: { count?: number; source?: string; warnings?: string[] }
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
  counts?: Record<string, any>
  counts_scored?: Record<string, any>
  totals_summary?: Record<string, any>
  scoring?: Record<string, any>
  meta: Record<string, any>
  questions: Array<Record<string, any>>
  score_schema?: ExamScoreSchema
  answer_key?: Record<string, any>
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
  prompts: string[]
  examples: string[]
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
    prompts?: string[]
    examples?: string[]
    allowed_roles?: string[]
  }>
}

export type WorkbenchTab = 'skills' | 'memory' | 'workflow'
export type WheelScrollZone = 'chat' | 'session' | 'workbench'

export type WorkflowStepState = 'todo' | 'active' | 'done' | 'error'
export type WorkflowIndicatorTone = 'neutral' | 'active' | 'success' | 'error'
export type WorkflowStepItem = { key: string; label: string; state: WorkflowStepState }
export type WorkflowIndicator = { label: string; tone: WorkflowIndicatorTone; steps: WorkflowStepItem[] }
