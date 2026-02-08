import type {
  ExamUploadDraft,
  ExamUploadJobStatus,
  UploadDraft,
  UploadJobStatus,
  WorkflowIndicator,
  WorkflowIndicatorTone,
  WorkflowStepItem,
  WorkflowStepState,
} from '../../appTypes'

type AssignmentArgs = {
  uploadJobId: string
  uploadJobInfoStatus?: UploadJobStatus['status'] | string
  uploading: boolean
  uploadConfirming: boolean
  uploadDraft: UploadDraft | null
  uploadError: string
  draftError: string
  draftActionError: string
}

export function buildAssignmentWorkflowIndicator({
  uploadJobId,
  uploadJobInfoStatus,
  uploading,
  uploadConfirming,
  uploadDraft,
  uploadError,
  draftError,
  draftActionError,
}: AssignmentArgs): WorkflowIndicator {
  const steps: WorkflowStepItem[] = [
    { key: 'upload', label: '上传文件', state: 'todo' },
    { key: 'parse', label: '解析', state: 'todo' },
    { key: 'review', label: '审核草稿', state: 'todo' },
    { key: 'confirm', label: '创建作业', state: 'todo' },
  ]
  const setState = (key: WorkflowStepItem['key'], state: WorkflowStepState) => {
    const step = steps.find((item) => item.key === key)
    if (step) step.state = state
  }
  const markDone = (...keys: WorkflowStepItem['key'][]) => {
    keys.forEach((key) => setState(key, 'done'))
  }

  const status = uploadJobInfoStatus
  const hasError = Boolean(uploadError || draftError || draftActionError || status === 'failed' || status === 'cancelled')

  let label = '未开始'
  let tone: WorkflowIndicatorTone = 'neutral'
  let stage:
    | 'idle'
    | 'uploading'
    | 'parsing'
    | 'review'
    | 'confirming'
    | 'completed'
    | 'failed-parse'
    | 'failed-review'
    | 'failed-confirm' = 'idle'

  if (status === 'confirmed' || status === 'created') {
    stage = 'completed'
    label = '已创建作业'
    tone = 'success'
  } else if (uploadConfirming || status === 'confirming') {
    stage = 'confirming'
    label = '创建中'
    tone = 'active'
  } else if (status === 'done' || uploadDraft) {
    stage = 'review'
    label = '待审核'
    tone = 'active'
  } else if (uploading) {
    stage = 'uploading'
    label = '上传中'
    tone = 'active'
  } else if (status === 'queued' || status === 'processing' || uploadJobId) {
    stage = 'parsing'
    label = '解析中'
    tone = 'active'
  }

  if (hasError) {
    tone = 'error'
    if (status === 'failed' || status === 'cancelled' || uploadError) {
      stage = 'failed-parse'
      label = status === 'cancelled' ? '流程取消' : '解析失败'
    } else if (uploadConfirming || status === 'confirming') {
      stage = 'failed-confirm'
      label = '创建失败'
    } else {
      stage = 'failed-review'
      label = '审核异常'
    }
  }

  switch (stage) {
    case 'uploading':
      setState('upload', 'active')
      break
    case 'parsing':
      markDone('upload')
      setState('parse', 'active')
      break
    case 'review':
      markDone('upload', 'parse')
      setState('review', 'active')
      break
    case 'confirming':
      markDone('upload', 'parse', 'review')
      setState('confirm', 'active')
      break
    case 'completed':
      markDone('upload', 'parse', 'review', 'confirm')
      break
    case 'failed-parse':
      if (uploading) {
        setState('upload', 'error')
      } else {
        markDone('upload')
        setState('parse', 'error')
      }
      break
    case 'failed-review':
      markDone('upload', 'parse')
      setState('review', 'error')
      break
    case 'failed-confirm':
      markDone('upload', 'parse', 'review')
      setState('confirm', 'error')
      break
    default:
      break
  }

  return { label, tone, steps }
}

type ExamArgs = {
  examJobId: string
  examJobInfoStatus?: ExamUploadJobStatus['status'] | string
  examUploading: boolean
  examConfirming: boolean
  examDraft: ExamUploadDraft | null
  examUploadError: string
  examDraftError: string
  examDraftActionError: string
}

export function buildExamWorkflowIndicator({
  examJobId,
  examJobInfoStatus,
  examUploading,
  examConfirming,
  examDraft,
  examUploadError,
  examDraftError,
  examDraftActionError,
}: ExamArgs): WorkflowIndicator {
  const steps: WorkflowStepItem[] = [
    { key: 'upload', label: '上传文件', state: 'todo' },
    { key: 'parse', label: '解析', state: 'todo' },
    { key: 'review', label: '审核草稿', state: 'todo' },
    { key: 'confirm', label: '创建考试', state: 'todo' },
  ]
  const setState = (key: WorkflowStepItem['key'], state: WorkflowStepState) => {
    const step = steps.find((item) => item.key === key)
    if (step) step.state = state
  }
  const markDone = (...keys: WorkflowStepItem['key'][]) => {
    keys.forEach((key) => setState(key, 'done'))
  }

  const status = examJobInfoStatus
  const hasError = Boolean(examUploadError || examDraftError || examDraftActionError || status === 'failed' || status === 'cancelled')

  let label = '未开始'
  let tone: WorkflowIndicatorTone = 'neutral'
  let stage:
    | 'idle'
    | 'uploading'
    | 'parsing'
    | 'review'
    | 'confirming'
    | 'completed'
    | 'failed-parse'
    | 'failed-review'
    | 'failed-confirm' = 'idle'

  if (status === 'confirmed') {
    stage = 'completed'
    label = '已创建考试'
    tone = 'success'
  } else if (examConfirming || status === 'confirming') {
    stage = 'confirming'
    label = '创建中'
    tone = 'active'
  } else if (status === 'done' || examDraft) {
    stage = 'review'
    label = '待审核'
    tone = 'active'
  } else if (examUploading) {
    stage = 'uploading'
    label = '上传中'
    tone = 'active'
  } else if (status === 'queued' || status === 'processing' || examJobId) {
    stage = 'parsing'
    label = '解析中'
    tone = 'active'
  }

  if (hasError) {
    tone = 'error'
    if (status === 'failed' || status === 'cancelled' || examUploadError) {
      stage = 'failed-parse'
      label = status === 'cancelled' ? '流程取消' : '解析失败'
    } else if (examConfirming || status === 'confirming') {
      stage = 'failed-confirm'
      label = '创建失败'
    } else {
      stage = 'failed-review'
      label = '审核异常'
    }
  }

  switch (stage) {
    case 'uploading':
      setState('upload', 'active')
      break
    case 'parsing':
      markDone('upload')
      setState('parse', 'active')
      break
    case 'review':
      markDone('upload', 'parse')
      setState('review', 'active')
      break
    case 'confirming':
      markDone('upload', 'parse', 'review')
      setState('confirm', 'active')
      break
    case 'completed':
      markDone('upload', 'parse', 'review', 'confirm')
      break
    case 'failed-parse':
      if (examUploading) {
        setState('upload', 'error')
      } else {
        markDone('upload')
        setState('parse', 'error')
      }
      break
    case 'failed-review':
      markDone('upload', 'parse')
      setState('review', 'error')
      break
    case 'failed-confirm':
      markDone('upload', 'parse', 'review')
      setState('confirm', 'error')
      break
    default:
      break
  }

  return { label, tone, steps }
}

