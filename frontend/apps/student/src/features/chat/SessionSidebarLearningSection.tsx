import type { SessionSidebarProps } from './sessionSidebarTypes'

type Props = Pick<
SessionSidebarProps,
| 'apiBase'
| 'dispatch'
| 'verifiedStudent'
| 'verifyOpen'
| 'handleVerify'
| 'nameInput'
| 'classInput'
| 'credentialInput'
| 'verifying'
| 'verifyError'
| 'verifyInfo'
| 'todayAssignment'
| 'assignmentLoading'
| 'assignmentError'
| 'resetVerification'
>

export default function SessionSidebarLearningSection(props: Props) {
  const {
    apiBase,
    dispatch,
    verifiedStudent,
    verifyOpen,
    handleVerify,
    nameInput,
    classInput,
    credentialInput,
    verifying,
    verifyError,
    verifyInfo,
    todayAssignment,
    assignmentLoading,
    assignmentError,
    resetVerification,
  } = props
  const todayDateStr = new Date().toLocaleDateString('sv-SE')
  const nameInputId = 'student-verify-name'
  const classInputId = 'student-verify-class'
  const credentialInputId = 'student-verify-credential'
  const verifyPanelId = 'student-verify-panel'

  return (
    <section className="border-t border-border pt-3 grid gap-2.5">
      <div className="flex justify-between items-center gap-2">
        <strong>学习概览</strong>
        <button
          type="button"
          className="ghost"
          aria-expanded={verifyOpen}
          aria-controls={verifyPanelId}
          onClick={() => dispatch({ type: 'SET', field: 'verifyOpen', value: !verifyOpen })}
        >
          {verifyOpen ? '收起' : '展开'}
        </button>
      </div>
      {verifiedStudent ? (
        <div className="text-xs text-muted">
          已认证：{verifiedStudent.class_name ? `${verifiedStudent.class_name} · ` : ''}{verifiedStudent.student_name}
        </div>
      ) : (
        <div className="text-xs text-muted">请先完成姓名/班级 + 密码认证后开始提问。</div>
      )}
      {verifyOpen && (
        <div id={verifyPanelId} className="grid gap-2.5">
          <form className="grid gap-2.5" onSubmit={handleVerify}>
            <div className="grid gap-1.5">
              <label htmlFor={nameInputId}>姓名</label>
              <input
                id={nameInputId}
                value={nameInput}
                onChange={(e) => dispatch({ type: 'SET', field: 'nameInput', value: e.target.value })}
                placeholder="例如：刘昊然"
                autoComplete="name"
              />
            </div>
            <div className="grid gap-1.5">
              <label htmlFor={classInputId}>班级（重名时必填）</label>
              <input
                id={classInputId}
                value={classInput}
                onChange={(e) => dispatch({ type: 'SET', field: 'classInput', value: e.target.value })}
                placeholder="例如：高二2403班"
                autoComplete="organization"
              />
            </div>
            <div className="grid gap-1.5">
              <label htmlFor={credentialInputId}>密码</label>
              <input
                id={credentialInputId}
                type="password"
                value={credentialInput}
                onChange={(e) => dispatch({ type: 'SET', field: 'credentialInput', value: e.target.value })}
                placeholder="输入老师分发或重置后的密码"
                autoComplete="current-password"
              />
            </div>
            <button
              type="submit"
              className="border-none rounded-[10px] px-3 py-[9px] bg-accent text-white cursor-pointer"
              disabled={verifying}
            >
              {verifying ? '认证中…' : '确认认证'}
            </button>
          </form>

          {verifyError && <div className="status err">{verifyError}</div>}
          {verifyInfo && <div className="status ok">{verifyInfo}</div>}
        </div>
      )}
      {verifiedStudent && (
        <div className="grid gap-1.5 rounded-[16px] border border-border bg-[color:var(--color-surface)] px-3 py-3">
          <div className="text-xs text-muted">今日任务（{todayAssignment?.date || todayDateStr}）</div>
          {assignmentLoading && <div className="text-xs text-muted">加载中…</div>}
          {assignmentError && <div className="text-xs text-muted">{assignmentError}</div>}
          {!assignmentLoading && !todayAssignment && !assignmentError && <div className="text-xs text-muted">今日任务准备中，可返回首页继续生成。</div>}
          {todayAssignment && (
            <>
              <div className="text-xs text-muted">
                作业编号：{todayAssignment.assignment_id || '-'} · 题数：{todayAssignment.question_count || 0}
              </div>
              {todayAssignment.meta?.target_kp?.length ? (
                <div className="text-xs text-muted">知识点：{todayAssignment.meta.target_kp.join('，')}</div>
              ) : null}
              {todayAssignment.delivery?.files?.length ? (
                <div className="grid gap-1.5">
                  {todayAssignment.delivery.files.map((file) => (
                    <a key={file.url} className="inline-flex items-center gap-1.5 rounded-[10px] border border-[color:var(--color-border)] bg-[color:var(--color-note)] px-2.5 py-1.5 text-[13px] text-ink no-underline" href={`${apiBase}${file.url}`} target="_blank" rel="noreferrer">
                      下载：{file.name}
                    </a>
                  ))}
                </div>
              ) : (
                <div className="text-xs text-muted">返回首页后，从“开始今日任务”进入练习。</div>
              )}
            </>
          )}
        </div>
      )}
      {verifiedStudent && (
        <button type="button" className="ghost" onClick={resetVerification}>重新认证</button>
      )}
    </section>
  )
}
