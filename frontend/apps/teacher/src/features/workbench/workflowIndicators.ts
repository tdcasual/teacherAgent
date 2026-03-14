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

type TeacherWorkflowGuidanceArgs = {
  mode: 'assignment' | 'exam'
  tone: WorkflowIndicator['tone']
  activeStepKey?: string
  hasExecutionTimeline: boolean
  hasProgressData: boolean
}

export type TeacherWorkflowGuidance = {
  nextStepLabel: string
  primaryActionLabel: string
  primaryActionTargetId: string
}

export function findActiveWorkflowStep(indicator: WorkflowIndicator) {
  return indicator.steps.find((step) => step.state === 'error')
    || indicator.steps.find((step) => step.state === 'active')
}

export function buildTeacherWorkflowGuidance({
  mode,
  tone,
  activeStepKey,
  hasExecutionTimeline,
  hasProgressData,
}: TeacherWorkflowGuidanceArgs): TeacherWorkflowGuidance {
  if (tone === 'error') {
    if (activeStepKey === 'confirm' || activeStepKey === 'review') {
      return {
        nextStepLabel: mode === 'assignment'
          ? '下一步：回到草稿并处理异常后，再确认创建作业'
          : '下一步：回到考试草稿并处理异常后，再确认创建考试',
        primaryActionLabel: mode === 'assignment' ? '查看草稿' : '查看考试草稿',
        primaryActionTargetId: mode === 'assignment'
          ? 'workflow-assignment-draft-section'
          : 'workflow-exam-draft-section',
      }
    }

    return {
      nextStepLabel: mode === 'assignment'
        ? '下一步：检查上传材料并重新解析作业'
        : '下一步：检查考试材料并重新解析',
      primaryActionLabel: '去上传区',
      primaryActionTargetId: 'workflow-upload-section',
    }
  }

  if (activeStepKey === 'upload') {
    return {
      nextStepLabel: mode === 'assignment'
        ? '下一步：上传今天的作业材料'
        : '下一步：上传今天的考试材料',
      primaryActionLabel: '去上传区',
      primaryActionTargetId: 'workflow-upload-section',
    }
  }

  if (activeStepKey === 'parse') {
    return {
      nextStepLabel: mode === 'assignment'
        ? '下一步：查看解析进度并等待作业草稿生成'
        : '下一步：查看解析进度并等待考试草稿生成',
      primaryActionLabel: '查看上传区',
      primaryActionTargetId: 'workflow-upload-section',
    }
  }

  if (activeStepKey === 'review') {
    return {
      nextStepLabel: mode === 'assignment'
        ? '下一步：继续审核草稿并确认创建作业'
        : '下一步：继续审核考试草稿并确认创建考试',
      primaryActionLabel: mode === 'assignment' ? '查看草稿' : '查看考试草稿',
      primaryActionTargetId: mode === 'assignment'
        ? 'workflow-assignment-draft-section'
        : 'workflow-exam-draft-section',
    }
  }

  if (activeStepKey === 'confirm') {
    return {
      nextStepLabel: mode === 'assignment'
        ? '下一步：确认创建作业并跟进学生完成情况'
        : '下一步：确认创建考试并继续查看考试结果',
      primaryActionLabel: mode === 'assignment' ? '查看草稿' : '查看考试草稿',
      primaryActionTargetId: mode === 'assignment'
        ? 'workflow-assignment-draft-section'
        : 'workflow-exam-draft-section',
    }
  }

  if (tone === 'success') {
    if (mode === 'assignment') {
      return {
        nextStepLabel: hasProgressData
          ? '下一步：查看完成情况并跟进未完成学生'
          : '下一步：查看完成情况并开始跟进班级提交',
        primaryActionLabel: '查看完成情况',
        primaryActionTargetId: 'workflow-progress-section',
      }
    }

    return {
      nextStepLabel: '下一步：查看考试结果并继续回看成绩',
      primaryActionLabel: '查看考试结果',
      primaryActionTargetId: 'workflow-exam-draft-section',
    }
  }

  if (hasExecutionTimeline) {
    return {
      nextStepLabel: '下一步：查看最近一次执行结果',
      primaryActionLabel: '去上传区',
      primaryActionTargetId: 'workflow-upload-section',
    }
  }

  return {
    nextStepLabel: mode === 'assignment'
      ? '下一步：从上传区开始今天的作业流程'
      : '下一步：从上传区开始今天的考试流程',
    primaryActionLabel: '去上传区',
    primaryActionTargetId: 'workflow-upload-section',
  }
}

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
