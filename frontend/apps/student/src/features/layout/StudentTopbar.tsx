import type { Dispatch, SetStateAction } from 'react'
import type { VerifiedStudent } from '../../appTypes'

type Props = {
  verifiedStudent: VerifiedStudent | null

  sidebarOpen: boolean
  setSidebarOpen: Dispatch<SetStateAction<boolean>>
  startNewStudentSession: () => void
}

export default function StudentTopbar(props: Props) {
  const {
    verifiedStudent,
    sidebarOpen,
    setSidebarOpen,
    startNewStudentSession,
  } = props

  return (
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
        {verifiedStudent?.student_id ? (
          <span className="muted" style={{ fontSize: 12 }}>
            当前学生：{verifiedStudent.student_id}
          </span>
        ) : null}
      </div>
    </header>
  )
}
