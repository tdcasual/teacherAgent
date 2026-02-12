import type { ReactNode } from 'react'

type Props = {
  children: ReactNode
}

export default function StudentWorkbench(props: Props) {
  const { children } = props
  return (
    <section className="student-workbench" data-testid="student-workbench">
      {children}
    </section>
  )
}
