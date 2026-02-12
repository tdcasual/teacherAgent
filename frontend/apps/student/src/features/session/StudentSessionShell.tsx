import type { ReactNode } from 'react'

type Props = {
  sidebarOpen: boolean
  workbench: ReactNode
  chatPanel: ReactNode
}

export default function StudentSessionShell(props: Props) {
  const { sidebarOpen, workbench, chatPanel } = props

  return (
    <div className={`student-layout flex-1 min-h-0 overflow-hidden ${sidebarOpen ? 'sidebar-open' : 'sidebar-collapsed'}`}>
      {workbench}
      {chatPanel}
    </div>
  )
}
