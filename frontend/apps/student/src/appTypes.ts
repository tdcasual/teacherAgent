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

export type StudentHistoryMessage = {
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

export type AssignmentQuestion = {
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

export type VerifyResponse = {
  ok: boolean
  error?: string
  message?: string
  student?: VerifiedStudent
}
