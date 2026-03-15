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
      <div className="mx-auto grid max-w-[980px] gap-6">
        <TodayHero
          studentName={studentName}
          dateLabel={dateLabel}
          title={heroTitle}
          summary={heroSummary}
        />
        <TodayTaskCard viewModel={viewModel} onPrimaryAction={onPrimaryAction} />
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px] lg:items-start">
          <TaskMaterialList materials={viewModel.materials} />
          <LearningProgressRail steps={viewModel.progressSteps} />
        </div>
        <section className="grid gap-3 rounded-[24px] border border-border bg-[color:var(--color-note)] p-4" aria-labelledby="student-home-history-title">
          <h2 id="student-home-history-title" className="m-0 text-[16px] font-semibold text-ink">历史与补充</h2>
          <p className="m-0 text-[13px] leading-[1.55] text-muted">完成今天的主任务后，再查看历史记录或进入自由提问。</p>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="ghost" onClick={onOpenHistory}>查看历史任务</button>
            <button type="button" className="ghost" onClick={onOpenFreeChat}>自由提问</button>
          </div>
        </section>
      </div>
    </main>
  )
}
