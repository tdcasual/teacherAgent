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
    <section
      className="grid gap-2.5 rounded-[20px] bg-[color:color-mix(in_oklab,var(--color-surface-soft)_78%,white)] p-3.5"
      aria-labelledby="student-home-progress-title"
      data-testid="student-home-progress-stage"
      data-home-tier="supporting"
    >
      <h2 id="student-home-progress-title" className="m-0 text-[14px] font-semibold text-ink">学习进度</h2>
      <ol className="m-0 flex flex-wrap gap-2 p-0 list-none">
        {steps.map((step, index) => (
          <li
            key={`${step.label}-${index}`}
            className={`inline-flex min-h-[36px] items-center rounded-[999px] border px-3 py-2 text-[13px] shadow-none ${toneClassMap[step.tone]}`}
          >
            {step.label}
          </li>
        ))}
      </ol>
    </section>
  )
}
