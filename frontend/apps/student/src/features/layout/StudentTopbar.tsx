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
    <header className="flex justify-between items-center gap-3 px-4 py-2.5 bg-white/94 border-b border-border backdrop-blur-[8px] backdrop-saturate-[180%] sticky top-0 z-25 max-[900px]:items-start max-[900px]:flex-wrap">
      <div className="flex items-center gap-2 flex-wrap max-[900px]:w-full max-[900px]:justify-between">
        <div className="font-bold text-base tracking-[0.2px] max-[900px]:text-sm">物理学习助手 · 学生端</div>
        <button className="ghost" type="button" onClick={() => setSidebarOpen((prev) => !prev)}>
          {sidebarOpen ? '收起会话' : '展开会话'}
        </button>
        <button className="ghost" onClick={startNewStudentSession}>
          新会话
        </button>
      </div>
      <div className="flex items-center gap-2 max-[900px]:w-full max-[900px]:justify-between">
        <div className="role-badge student">身份：学生</div>
        {verifiedStudent?.student_id ? (
          <span className="muted">
            当前学生：{verifiedStudent.student_id}
          </span>
        ) : null}
      </div>
    </header>
  )
}
