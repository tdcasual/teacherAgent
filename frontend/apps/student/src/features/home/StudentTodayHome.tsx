import type { StudentTodayHomeViewModel } from '../../appTypes'
import LearningProgressRail from './LearningProgressRail'
import TaskMaterialList from './TaskMaterialList'
import TodayHero from './TodayHero'
import TodayTaskCard from './TodayTaskCard'

type StudentTodayHomeProps = {
  studentName: string
  dateLabel: string
  heroTitle: string
  heroSummary: string
  viewModel: StudentTodayHomeViewModel
  onPrimaryAction: () => void
  onOpenHistory: () => void
  onOpenFreeChat: () => void
}

export default function StudentTodayHome({
  studentName,
  dateLabel,
  heroTitle,
  heroSummary,
  viewModel,
  onPrimaryAction,
  onOpenHistory,
  onOpenFreeChat,
}: StudentTodayHomeProps) {
  return (
    <main className="flex-1 min-h-0 overflow-y-auto bg-[color:var(--color-app-bg)] px-4 py-5 md:px-6 md:py-6" data-testid="student-today-home">
      <div className="mx-auto grid max-w-[980px] gap-7">
        <section
          className="grid gap-5 rounded-[32px] border border-[color:color-mix(in_oklab,var(--color-accent)_10%,var(--color-border))] bg-[color:color-mix(in_oklab,var(--color-task-strip)_70%,white)] px-5 py-5 shadow-[0_18px_44px_rgba(148,163,184,0.12)] md:px-6 md:py-6"
          data-testid="student-today-primary-stage"
        >
          <TodayHero
            studentName={studentName}
            dateLabel={dateLabel}
            title={heroTitle}
            summary={heroSummary}
          />
          <TodayTaskCard viewModel={viewModel} onPrimaryAction={onPrimaryAction} />
        </section>
        <section
          className="grid gap-5 rounded-[28px] border border-[color:color-mix(in_oklab,var(--color-border)_86%,white)] bg-[color:color-mix(in_oklab,var(--color-note)_44%,white)] px-4 py-4 md:px-5 md:py-5"
          data-testid="student-today-secondary-stage"
        >
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_280px] lg:items-start">
            <TaskMaterialList materials={viewModel.materials} />
            <LearningProgressRail steps={viewModel.progressSteps} />
          </div>
          <section className="grid gap-2 border-t border-[color:color-mix(in_oklab,var(--color-border)_72%,white)] pt-4" aria-labelledby="student-home-history-title">
            <div className="flex flex-wrap items-center gap-2">
              <h2 id="student-home-history-title" className="m-0 text-[14px] font-semibold tracking-[0.04em] text-ink">历史与补充</h2>
              <span className="text-[11px] uppercase tracking-[0.14em] text-muted">按需查看</span>
            </div>
            <p className="m-0 text-[13px] leading-[1.55] text-muted">完成今天的主任务后，再查看历史记录或进入自由提问。</p>
            <div className="flex flex-wrap gap-2">
              <button type="button" className="ghost" onClick={onOpenHistory}>查看历史任务</button>
              <button type="button" className="ghost" onClick={onOpenFreeChat}>自由提问</button>
            </div>
          </section>
        </section>
      </div>
    </main>
  )
}
