import type { StudentTodayHomeViewModel } from '../../appTypes'
import LearningProgressRail from './LearningProgressRail'
import TaskMaterialList from './TaskMaterialList'
import TodayHero from './TodayHero'
import TodayTaskCard from './TodayTaskCard'

type StudentTodayHomeProps = {
  dateLabel: string
  viewModel: StudentTodayHomeViewModel
  onPrimaryAction: () => void
  onOpenHistory: () => void
  onOpenFreeChat: () => void
}

export default function StudentTodayHome({
  dateLabel,
  viewModel,
  onPrimaryAction,
  onOpenHistory,
  onOpenFreeChat,
}: StudentTodayHomeProps) {
  return (
    <main className="flex-1 min-h-0 overflow-y-auto bg-[color:var(--color-app-bg)] px-4 py-5 md:px-6 md:py-6" data-testid="student-today-home">
      <div className="mx-auto grid max-w-[920px] gap-4 md:gap-5">
        <section
          className="grid gap-3 rounded-[24px] border border-[color:color-mix(in_oklab,var(--color-accent)_10%,var(--color-border))] bg-[linear-gradient(180deg,color-mix(in_oklab,var(--color-surface)_96%,white)_0%,color-mix(in_oklab,var(--color-task-strip)_48%,white)_100%)] px-4 py-4 shadow-[0_10px_24px_rgba(148,163,184,0.08)] md:px-5 md:py-4"
          data-testid="student-today-primary-stage"
          data-home-style="compact"
        >
          <TodayHero dateLabel={dateLabel} />
          <TodayTaskCard viewModel={viewModel} onPrimaryAction={onPrimaryAction} />
        </section>
        <section
          className="grid gap-4 rounded-[22px] border border-[color:color-mix(in_oklab,var(--color-border)_70%,white)] bg-[color:color-mix(in_oklab,var(--color-note)_18%,white)] px-4 py-4 md:px-5 md:py-4"
          data-testid="student-today-secondary-stage"
        >
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_240px] lg:items-start">
            <TaskMaterialList materials={viewModel.materials} />
            <LearningProgressRail steps={viewModel.progressSteps} />
          </div>
          <section
            className="flex flex-wrap items-center gap-2 border-t border-[color:color-mix(in_oklab,var(--color-border)_62%,white)] pt-3"
            aria-label="更多入口"
            data-testid="student-home-history-stage"
            data-home-tier="supporting"
            data-home-style="inline-links"
          >
            <button type="button" className="student-supporting-link" onClick={onOpenHistory}>历史任务</button>
            <button type="button" className="student-supporting-link" onClick={onOpenFreeChat}>自由提问</button>
          </section>
        </section>
      </div>
    </main>
  )
}
