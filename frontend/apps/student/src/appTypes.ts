export type Message = {
  id: string
  role: 'user' | 'assistant'
  content: string
  time: string
}

export type RenderedMessage = Message & { html: string }

export type PendingChatJob = {
  job_id: string
  request_id: string
  placeholder_id: string
  user_text: string
  session_id: string
  created_at: number
}

export type ChatJobStatus = {
  job_id: string
  status: 'queued' | 'processing' | 'done' | 'failed' | 'cancelled' | string
  step?: string
  reply?: string
  error?: string
  error_detail?: string
  updated_at?: string
}

export type RecentCompletedReply = {
  session_id: string
  user_text: string
  reply_text: string
  completed_at: number
}

export type ChatStartResult = {
  ok: boolean
  job_id: string
  status: string
  warnings?: string[]
}

export type StudentHistorySession = {
  session_id: string
  updated_at?: string
  message_count?: number
  preview?: string
  assignment_id?: string
  date?: string
}

export type SessionGroup<T> = {
  key: string
  label: string
  items: T[]
}

export type StudentHistorySessionsResponse = {
  ok: boolean
  student_id: string
  sessions: StudentHistorySession[]
  next_cursor?: number | null
  total?: number
}

type StudentHistoryMessage = {
  ts?: string
  role?: string
  content?: string
  [k: string]: unknown
}

export type StudentHistorySessionResponse = {
  ok: boolean
  student_id: string
  session_id: string
  messages: StudentHistoryMessage[]
  next_cursor: number
}

type AssignmentQuestion = {
  question_id?: string
  kp_id?: string
  difficulty?: string
  stem_text?: string
}

export type AssignmentDetail = {
  assignment_id: string
  date?: string
  question_count?: number
  meta?: { target_kp?: string[] }
  questions?: AssignmentQuestion[]
  delivery?: { mode?: string; files?: Array<{ name: string; url: string }> }
}

export type VerifiedStudent = {
  student_id: string
  student_name: string
  class_name?: string
}

export type StudentTodayHomeStatus =
  | 'pending_generation'
  | 'generating'
  | 'ready'
  | 'in_progress'
  | 'submitted'

export type StudentTodayHomeMaterial = {
  label: string
  url?: string
}

export type StudentTodayHomeStep = {
  label: string
  tone: 'neutral' | 'active' | 'success'
}

export type StudentTodayHomeViewModel = {
  status: StudentTodayHomeStatus
  title: string
  summary: string
  primaryActionLabel: string
  primaryActionDisabled: boolean
  statusLabel: string
  estimatedMinutes: number | null
  dueLabel: string
  materials: StudentTodayHomeMaterial[]
  progressSteps: StudentTodayHomeStep[]
}

export type StudentVerifyCandidate = {
  candidate_id: string
  student: VerifiedStudent
  password_set?: boolean
}

export type StudentIdentifyResponse = {
  ok: boolean
  error?: string
  message?: string
  candidate_id?: string
  student?: VerifiedStudent
  password_set?: boolean
  candidates?: StudentVerifyCandidate[]
}

export type StudentLoginResponse = {
  ok: boolean
  error?: string
  message?: string
  access_token?: string
  expires_in?: number
  role?: string
  subject_id?: string
  student?: VerifiedStudent
  password_set?: boolean
}
