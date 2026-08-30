import { useMemo, useState } from 'react'
import type { ChatSubmitAttachment, StudentSubmitResult } from './studentSubmit'
import { postStudentSubmit } from './studentSubmit'

type StudentSubmitPanelProps = {
  apiBase: string
  studentId: string
  assignmentId: string
  assignmentTitle: string
  chatAttachments: ChatSubmitAttachment[]
  chatFiles: File[]
  onClose: () => void
  onSubmitted: (result: StudentSubmitResult) => void
}

const filesFromList = (list: FileList | null): File[] => (list ? Array.from(list) : [])

export default function StudentSubmitPanel({
  apiBase,
  studentId,
  assignmentId,
  assignmentTitle,
  chatAttachments,
  chatFiles,
  onClose,
  onSubmitted,
}: StudentSubmitPanelProps) {
  const [pickedFiles, setPickedFiles] = useState<File[]>([])
  const [chatConfirmArmed, setChatConfirmArmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<StudentSubmitResult | null>(null)
  const [error, setError] = useState('')

  const previewNames = useMemo(() => {
    if (chatConfirmArmed) return chatAttachments.map((item) => item.fileName).filter(Boolean)
    return pickedFiles.map((file) => file.name)
  }, [chatConfirmArmed, chatAttachments, pickedFiles])

  const submitFiles = (): File[] => {
    if (chatConfirmArmed) return chatFiles.filter((file) => Boolean(file?.name))
    return pickedFiles
  }

  const runSubmit = async () => {
    const files = submitFiles()
    if (!files.length) {
      setError('请先选择要提交的作业文件')
      return
    }
    setBusy(true)
    setError('')
    try {
      const next = await postStudentSubmit({
        apiBase,
        studentId,
        assignmentId,
        files,
      })
      setResult(next)
      if (next.submitted) onSubmitted(next)
    } catch {
      setError('提交失败，请稍后重试。')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="flex-1 min-h-0 overflow-y-auto bg-[color:var(--color-app-bg)] px-4 py-5 md:px-6 md:py-6" data-testid="student-submit-panel">
      <div className="mx-auto grid max-w-[720px] gap-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h1 className="m-0 text-[20px] font-semibold text-ink">提交作业</h1>
          <button type="button" className="student-supporting-link" onClick={onClose}>返回</button>
        </div>
        <p className="m-0 text-[14px] text-muted">
          {assignmentTitle || assignmentId}。聊天与附件只是陪练，不会记为提交。
        </p>
        <section className="grid gap-3 rounded-[20px] border border-border bg-white px-4 py-4">
          <label className="grid gap-2 text-[13px] font-medium text-ink">
            选择提交文件
            <input
              type="file"
              multiple
              aria-label="选择提交文件"
              accept="application/pdf,image/*,.txt,.md,.csv"
              onChange={(event) => {
                setPickedFiles(filesFromList(event.target.files))
                setChatConfirmArmed(false)
                setResult(null)
                event.currentTarget.value = ''
              }}
            />
          </label>
          {chatAttachments.length ? (
            <button
              type="button"
              className="student-supporting-link justify-self-start"
              onClick={() => {
                setChatConfirmArmed(true)
                setResult(null)
                setError('')
              }}
            >
              把当前聊天附件作为本次提交
            </button>
          ) : null}
          {previewNames.length ? (
            <ul className="m-0 grid gap-1 p-0 list-none text-[13px]" data-testid="student-submit-preview">
              {previewNames.map((name) => (
                <li key={name} className="rounded-[12px] border border-border px-3 py-2">{name}</li>
              ))}
            </ul>
          ) : null}
          {chatConfirmArmed ? (
            <button
              type="button"
              className="inline-flex min-h-[44px] items-center justify-center rounded-[14px] border-none bg-accent px-4 py-2 text-[13px] font-medium text-white disabled:opacity-60"
              disabled={busy}
              onClick={() => { void runSubmit() }}
            >
              确认提交
            </button>
          ) : (
            <button
              type="button"
              className="inline-flex min-h-[44px] items-center justify-center rounded-[14px] border-none bg-accent px-4 py-2 text-[13px] font-medium text-white disabled:opacity-60"
              disabled={busy || !pickedFiles.length}
              onClick={() => { void runSubmit() }}
            >
              提交作业
            </button>
          )}
          {error ? <div className="text-[13px] text-[color:var(--color-danger)]">{error}</div> : null}
          {result?.submitted ? (
            <div className="rounded-[14px] border border-[color:var(--color-success)] bg-[color:var(--color-success-soft)] px-3 py-2 text-[13px]" data-testid="student-submit-success">
              <span data-testid="student-submit-result">{result.message}</span>
            </div>
          ) : null}
          {result && !result.submitted && result.ok ? (
            <div className="rounded-[14px] border border-[color:var(--color-danger)] bg-[color:var(--color-danger-soft)] px-3 py-2 text-[13px]" data-testid="student-submit-not-counted">
              <span data-testid="student-submit-result">{result.message}</span>
            </div>
          ) : null}
          {result && !result.ok ? (
            <div className="text-[13px] text-[color:var(--color-danger)]">{result.message}</div>
          ) : null}
        </section>
      </div>
    </main>
  )
}
