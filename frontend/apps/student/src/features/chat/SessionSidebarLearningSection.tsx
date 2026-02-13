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
| 'verifying'
| 'verifyError'
| 'todayAssignment'
| 'assignmentLoading'
| 'assignmentError'
| 'resetVerification'
>

export default function SessionSidebarLearningSection(props: Props) {
  const {
    apiBase, dispatch, verifiedStudent, verifyOpen, handleVerify, nameInput, classInput,
    verifying, verifyError, todayAssignment, assignmentLoading, assignmentError, resetVerification,
  } = props
  const todayDateStr = new Date().toLocaleDateString('sv-SE')
  const nameInputId = 'student-verify-name'
  const classInputId = 'student-verify-class'
  const verifyPanelId = 'student-verify-panel'

  return (
    <section className="border-t border-border pt-2.5 grid gap-2">
      <div className="flex justify-between items-center gap-2">
        <strong>学习信息</strong>
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
          已验证：{verifiedStudent.class_name ? `${verifiedStudent.class_name} · ` : ''}{verifiedStudent.student_name}
        </div>
      ) : (
        <div className="text-xs text-muted">请先完成姓名验证后开始提问。</div>
      )}
      {verifyOpen && (
        <form id={verifyPanelId} className="grid gap-2.5" onSubmit={handleVerify}>
          <div className="grid gap-1.5">
            <label htmlFor={nameInputId}>姓名</label>
            <input id={nameInputId} value={nameInput} onChange={(e) => dispatch({ type: 'SET', field: 'nameInput', value: e.target.value })} placeholder="例如：刘昊然" autoComplete="name" />
          </div>
          <div className="grid gap-1.5">
            <label htmlFor={classInputId}>班级（重名时必填）</label>
            <input id={classInputId} value={classInput} onChange={(e) => dispatch({ type: 'SET', field: 'classInput', value: e.target.value })} placeholder="例如：高二2403班" autoComplete="organization" />
          </div>
          <button type="submit" className="border-none rounded-[10px] px-3 py-[9px] bg-accent text-white cursor-pointer" disabled={verifying}>
            {verifying ? '验证中…' : '确认身份'}
          </button>
          {verifyError && <div className="status err">{verifyError}</div>}
        </form>
      )}
      {verifiedStudent && (
        <div className="grid gap-1.5">
          <div className="text-xs text-muted">今日作业（{todayAssignment?.date || todayDateStr}）</div>
          {assignmentLoading && <div className="text-xs text-muted">加载中…</div>}
          {assignmentError && <div className="text-xs text-muted">{assignmentError}</div>}
          {!assignmentLoading && !todayAssignment && !assignmentError && <div className="text-xs text-muted">今日暂无作业。</div>}
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
                    <a key={file.url} className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-[10px] bg-[#ecfaf5] text-[#0f766e] no-underline text-[13px] border border-[#cff0e6]" href={`${apiBase}${file.url}`} target="_blank" rel="noreferrer">
                      下载：{file.name}
                    </a>
                  ))}
                </div>
              ) : (
                <div className="text-xs text-muted">在聊天中输入"开始今天作业"进入讨论。</div>
              )}
            </>
          )}
        </div>
      )}
      {verifiedStudent && (
        <button type="button" className="ghost" onClick={resetVerification}>重新验证</button>
      )}
    </section>
  )
}
