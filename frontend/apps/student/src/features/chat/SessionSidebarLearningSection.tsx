import type { SessionSidebarProps } from './sessionSidebarTypes'

type Props = Pick<
SessionSidebarProps,
| 'apiBase'
| 'dispatch'
| 'verifiedStudent'
| 'verifyOpen'
| 'handleVerify'
| 'handleSetPassword'
| 'nameInput'
| 'classInput'
| 'credentialInput'
| 'credentialType'
| 'newPasswordInput'
| 'verifying'
| 'settingPassword'
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
    handleSetPassword,
    nameInput,
    classInput,
    credentialInput,
    credentialType,
    newPasswordInput,
    verifying,
    settingPassword,
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
  const newPasswordInputId = 'student-verify-new-password'
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
          已认证：{verifiedStudent.class_name ? `${verifiedStudent.class_name} · ` : ''}{verifiedStudent.student_name}
        </div>
      ) : (
        <div className="text-xs text-muted">请先完成姓名/班级 + token(或密码)认证后开始提问。</div>
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
              <label>认证方式</label>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  className={`ghost ${credentialType === 'token' ? 'font-semibold' : ''}`}
                  onClick={() => dispatch({ type: 'SET', field: 'credentialType', value: 'token' })}
                >
                  token
                </button>
                <button
                  type="button"
                  className={`ghost ${credentialType === 'password' ? 'font-semibold' : ''}`}
                  onClick={() => dispatch({ type: 'SET', field: 'credentialType', value: 'password' })}
                >
                  密码
                </button>
              </div>
            </div>
            <div className="grid gap-1.5">
              <label htmlFor={credentialInputId}>{credentialType === 'token' ? 'token' : '密码'}</label>
              <input
                id={credentialInputId}
                type={credentialType === 'token' ? 'text' : 'password'}
                value={credentialInput}
                onChange={(e) => dispatch({ type: 'SET', field: 'credentialInput', value: e.target.value })}
                placeholder={credentialType === 'token' ? '输入分发的 token' : '输入已设置密码'}
                autoComplete={credentialType === 'token' ? 'off' : 'current-password'}
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

          <form className="grid gap-2.5 border border-border rounded-[10px] p-2.5 bg-surface-soft" onSubmit={handleSetPassword}>
            <div className="text-xs text-muted">使用当前 token 或密码设置新密码（设置后 token 仍可登录）</div>
            <div className="grid gap-1.5">
              <label htmlFor={newPasswordInputId}>新密码</label>
              <input
                id={newPasswordInputId}
                type="password"
                value={newPasswordInput}
                onChange={(e) => dispatch({ type: 'SET', field: 'newPasswordInput', value: e.target.value })}
                placeholder="至少 8 位，含字母和数字"
                autoComplete="new-password"
              />
            </div>
            <button
              type="submit"
              className="border-none rounded-[10px] px-3 py-[9px] bg-[#0f766e] text-white cursor-pointer"
              disabled={settingPassword}
            >
              {settingPassword ? '设置中…' : '设置密码'}
            </button>
          </form>

          {verifyError && <div className="status err">{verifyError}</div>}
          {verifyInfo && <div className="status ok">{verifyInfo}</div>}
        </div>
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
        <button type="button" className="ghost" onClick={resetVerification}>重新认证</button>
      )}
    </section>
  )
}
