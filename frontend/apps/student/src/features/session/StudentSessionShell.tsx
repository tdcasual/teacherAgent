import type { ReactNode } from 'react'

type Props = {
  sidebarOpen: boolean
  workbench: ReactNode
  chatPanel: ReactNode
}

export default function StudentSessionShell(props: Props) {
  const { sidebarOpen, workbench, chatPanel } = props

  return (
    <div className={`student-layout ${sidebarOpen ? 'sidebar-open' : 'sidebar-collapsed'}`}>
      {workbench}
      {chatPanel}
    </div>
  )
}
