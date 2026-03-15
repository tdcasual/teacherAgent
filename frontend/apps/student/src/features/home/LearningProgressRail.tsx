import type { StudentTodayHomeStep } from '../../appTypes'

type LearningProgressRailProps = {
  steps: StudentTodayHomeStep[]
}

const toneClassMap: Record<StudentTodayHomeStep['tone'], string> = {
  neutral: 'bg-[color:var(--color-progress)] text-muted border-border',
  active: 'bg-accent-soft text-accent border-[color:var(--color-accent)]',
  success: 'bg-[color:color-mix(in_oklab,var(--color-success)_14%,white)] text-[color:var(--color-success)] border-[color:color-mix(in_oklab,var(--color-success)_35%,white)]',
}

export default function LearningProgressRail({ steps }: LearningProgressRailProps) {
  return (
    <section className="grid gap-3" aria-labelledby="student-home-progress-title">
      <h2 id="student-home-progress-title" className="m-0 text-[16px] font-semibold text-ink">学习进度</h2>
      <ol className="m-0 grid gap-2 p-0 list-none">
        {steps.map((step, index) => (
          <li key={`${step.label}-${index}`} className={`inline-flex items-center rounded-[16px] border px-3 py-2 text-[13px] ${toneClassMap[step.tone]}`}>
            {step.label}
          </li>
        ))}
      </ol>
    </section>
  )
}
