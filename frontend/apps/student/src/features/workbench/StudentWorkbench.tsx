import type { ReactNode } from 'react'

type Props = {
  children: ReactNode
}

export default function StudentWorkbench(props: Props) {
  const { children } = props
  return (
    <section className="min-h-0 overflow-hidden" data-testid="student-workbench">
      {children}
    </section>
  )
}
