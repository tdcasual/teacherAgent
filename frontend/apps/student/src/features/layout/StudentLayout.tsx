import type { ReactNode } from 'react'

type Props = {
  sidebarOpen: boolean
  sidebar: ReactNode
  chat: ReactNode
}

export default function StudentLayout({ sidebarOpen, sidebar, chat }: Props) {
  return (
    <div className={`student-layout ${sidebarOpen ? '' : 'sidebar-collapsed'}`}>
      {sidebar}
      {chat}
    </div>
  )
}
