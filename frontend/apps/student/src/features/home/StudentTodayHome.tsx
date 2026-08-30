import type { StudentTodayHomeItem, StudentTodayHomeViewModel } from '../../appTypes'
import LearningProgressRail from './LearningProgressRail'
import TaskMaterialList from './TaskMaterialList'
import TodayHero from './TodayHero'
import TodayTaskCard from './TodayTaskCard'

type StudentTodayHomeProps = {
  dateLabel: string
  viewModel: StudentTodayHomeViewModel
  onPrimaryAction: () => void
  onOpenAssignment?: (assignmentId: string) => void
  onOpenHistory: () => void
  onOpenFreeChat: () => void
  onOpenAssignmentHistory: () => void
  onOpenSubmit?: (assignmentId: string) => void
}

const groupBySubject = (items: StudentTodayHomeItem[]): Array<{ subject_id: string; items: StudentTodayHomeItem[] }> => {
  const groups: Array<{ subject_id: string; items: StudentTodayHomeItem[] }> = []
  const index = new Map<string, number>()
  for (const item of items) {
    const key = item.subject_id || '未分科'
    const existing = index.get(key)
    if (existing === undefined) {
      index.set(key, groups.length)
      groups.push({ subject_id: key, items: [item] })
      continue
    }
    groups[existing].items.push(item)
  }
  return groups
}

export default function StudentTodayHome({
  dateLabel,
  viewModel,
  onPrimaryAction,
  onOpenAssignment,
  onOpenHistory,
  onOpenFreeChat,
  onOpenAssignmentHistory,
  onOpenSubmit,
}: StudentTodayHomeProps) {
  const groups = groupBySubject(viewModel.items)
  const showList = viewModel.items.length > 0 && viewModel.status !== 'generating' && viewModel.status !== 'pending_generation'

  return (
    <main className="flex-1 min-h-0 overflow-y-auto bg-[color:var(--color-app-bg)] px-4 py-5 md:px-6 md:py-6" data-testid="student-today-home">
      <div className="mx-auto grid max-w-[920px] gap-4 md:gap-5">
        <section
          className="grid gap-3 rounded-[24px] border border-[color:color-mix(in_oklab,var(--color-accent)_8%,var(--color-border))] bg-[linear-gradient(180deg,color-mix(in_oklab,var(--color-surface)_98%,white)_0%,color-mix(in_oklab,var(--color-task-strip)_62%,white)_100%)] px-4 py-4 shadow-[0_10px_24px_rgba(9,30,66,0.08)] md:px-5 md:py-4"
          data-testid="student-today-primary-stage"
          data-home-style="compact"
        >
          <TodayHero dateLabel={dateLabel} />
          <TodayTaskCard viewModel={viewModel} onPrimaryAction={onPrimaryAction} />
          {showList ? (
            <div className="grid gap-3" data-testid="student-today-assignment-list">
              {groups.map((group) => (
                <section key={group.subject_id} className="grid gap-2">
                  <h2 className="m-0 text-[13px] font-medium text-muted">{group.subject_id}</h2>
                  {group.items.map((item) => (
                    <div
                      key={`${item.subject_id}:${item.teacher_id}:${item.assignment_id}`}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-[16px] border border-border bg-white px-3 py-3"
                    >
                      <div className="min-w-0 grid gap-1">
                        <div className="text-[15px] font-medium text-ink">{item.title}</div>
                        <div className="text-[12px] text-muted">
                          {item.overdue ? '逾期未交 · ' : ''}{item.dueLabel}
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          className="inline-flex min-h-[44px] items-center justify-center rounded-[14px] border-none bg-accent px-4 py-2 text-[13px] font-medium text-white"
                          onClick={() => (onOpenAssignment ? onOpenAssignment(item.assignment_id) : onPrimaryAction())}
                        >
                          进入任务
                        </button>
                        {onOpenSubmit && !item.submitted ? (
                          <button
                            type="button"
                            className="inline-flex min-h-[44px] items-center justify-center rounded-[14px] border border-border bg-white px-4 py-2 text-[13px] font-medium text-ink"
                            onClick={() => onOpenSubmit(item.assignment_id)}
                          >
                            提交作业
                          </button>
                        ) : null}
                      </div>
                    </div>
                  ))}
                </section>
              ))}
            </div>
          ) : null}
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
            <button type="button" className="student-supporting-link" onClick={onOpenAssignmentHistory}>作业记录</button>
            <button type="button" className="student-supporting-link" onClick={onOpenFreeChat}>自由提问</button>
          </section>
        </section>
      </div>
    </main>
  )
}
