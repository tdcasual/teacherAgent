import type { StudentTodayHomeMaterial } from '../../appTypes'

type TaskMaterialListProps = {
  materials: StudentTodayHomeMaterial[]
}

export default function TaskMaterialList({ materials }: TaskMaterialListProps) {
  return (
    <section
      className="grid gap-2.5 rounded-[20px] bg-[color:color-mix(in_oklab,var(--color-note)_44%,white)] p-3.5"
      aria-labelledby="student-home-materials-title"
      data-testid="student-home-materials-stage"
      data-home-tier="supporting"
    >
      <div className="flex items-center justify-between gap-3">
        <h2 id="student-home-materials-title" className="m-0 text-[14px] font-semibold text-ink">准备材料</h2>
        <span className="text-[12px] text-muted">{materials.length} 份</span>
      </div>
      {materials.length ? (
        <ul className="m-0 grid gap-1.5 p-0 list-none">
          {materials.map((item) => (
            <li
              key={`${item.label}-${item.url || ''}`}
              className="rounded-[16px] border border-[color:color-mix(in_oklab,var(--color-border)_74%,white)] bg-[color:color-mix(in_oklab,var(--color-surface)_88%,white)] px-3 py-2.5"
            >
              {item.url ? (
                <a className="text-[14px] font-medium text-ink no-underline" href={item.url}>
                  {item.label}
                </a>
              ) : (
                <span className="text-[14px] font-medium text-ink">{item.label}</span>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <div className="text-[13px] text-muted">任务生成后，这里会出现题目材料和老师说明。</div>
      )}
    </section>
  )
}
