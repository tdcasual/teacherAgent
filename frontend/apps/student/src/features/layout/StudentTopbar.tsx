import type { Dispatch, SetStateAction } from 'react'
import type { VerifiedStudent } from '../../appTypes'

type Props = {
  apiBase: string
  setApiBase: Dispatch<SetStateAction<string>>
  verifiedStudent: VerifiedStudent | null

  sidebarOpen: boolean
  setSidebarOpen: Dispatch<SetStateAction<boolean>>
  startNewStudentSession: () => void

  settingsOpen: boolean
  setSettingsOpen: Dispatch<SetStateAction<boolean>>
}

export default function StudentTopbar(props: Props) {
  const {
    apiBase,
    setApiBase,
    verifiedStudent,
    sidebarOpen,
    setSidebarOpen,
    startNewStudentSession,
    settingsOpen,
    setSettingsOpen,
  } = props

  return (
    <>
      <header className="topbar">
        <div className="top-left">
          <div className="brand">物理学习助手 · 学生端</div>
          <button className="ghost" type="button" onClick={() => setSidebarOpen((prev) => !prev)}>
            {sidebarOpen ? '收起会话' : '展开会话'}
          </button>
          <button className="ghost" onClick={startNewStudentSession}>
            新会话
          </button>
        </div>
        <div className="top-actions">
          <div className="role-badge student">身份：学生</div>
          <button className="ghost" onClick={() => setSettingsOpen((prev) => !prev)}>
            设置
          </button>
        </div>
      </header>

      {settingsOpen && (
        <section className="settings">
          <div className="settings-row">
            <label>接口地址</label>
            <input value={apiBase} onChange={(e) => setApiBase(e.target.value)} placeholder="http://localhost:8000" />
          </div>
          <div className="settings-hint">
            修改后立即生效。{verifiedStudent?.student_id ? ` 当前学生：${verifiedStudent.student_id}` : ''}
          </div>
        </section>
      )}
    </>
  )
}

