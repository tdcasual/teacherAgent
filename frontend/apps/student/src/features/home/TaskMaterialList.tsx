import type { StudentTodayHomeMaterial } from '../../appTypes'

type TaskMaterialListProps = {
  materials: StudentTodayHomeMaterial[]
}

export default function TaskMaterialList({ materials }: TaskMaterialListProps) {
  return (
    <section className="grid gap-3" aria-labelledby="student-home-materials-title">
      <div className="flex items-center justify-between gap-3">
        <h2 id="student-home-materials-title" className="m-0 text-[15px] font-semibold text-ink">准备材料</h2>
        <span className="text-[12px] text-muted">{materials.length} 份</span>
      </div>
      {materials.length ? (
        <ul className="m-0 grid gap-2 p-0 list-none">
          {materials.map((item) => (
            <li key={`${item.label}-${item.url || ''}`} className="rounded-[18px] border border-[color:color-mix(in_oklab,var(--color-border)_78%,white)] bg-[color:color-mix(in_oklab,var(--color-note)_62%,white)] px-4 py-3">
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
        <div className="rounded-[18px] border border-dashed border-border bg-[color:var(--color-note)] px-4 py-4 text-[13px] text-muted">
          任务生成后，这里会显示题目材料和老师说明。
        </div>
      )}
    </section>
  )
}
