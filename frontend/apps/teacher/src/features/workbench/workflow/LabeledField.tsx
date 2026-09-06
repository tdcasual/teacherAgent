import { cloneElement, useId, type ReactElement } from 'react'

export default function LabeledField({
  label,
  children,
  className = 'grid gap-1.5',
}: {
  label: string
  children: ReactElement<{ id?: string }>
  className?: string
}) {
  const id = useId()
  return (
    <div className={className}>
      <label htmlFor={id}>{label}</label>
      {cloneElement(children, { id })}
    </div>
  )
}
