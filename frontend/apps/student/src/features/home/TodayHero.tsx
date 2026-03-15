type TodayHeroProps = {
  studentName: string
  dateLabel: string
  title: string
  summary: string
}

export default function TodayHero({ studentName, dateLabel, title, summary }: TodayHeroProps) {
  return (
    <section className="grid gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[12px] font-medium tracking-[0.08em] text-muted">{dateLabel}</span>
        <span className="inline-flex items-center rounded-full border border-[color:color-mix(in_oklab,var(--color-accent)_12%,var(--color-border))] bg-[color:color-mix(in_oklab,var(--color-surface-soft)_78%,white)] px-2.5 py-1 text-[11px] font-semibold tracking-[0.14em] text-muted">
          TODAY FIRST
        </span>
      </div>
      <div className="grid gap-1">
        <h1 className="m-0 text-[clamp(28px,4vw,40px)] leading-[1.05] font-semibold text-ink">{title}</h1>
        <p className="m-0 max-w-[42rem] text-[14px] leading-[1.5] text-muted">
          {studentName ? `${studentName}，${summary}` : summary}
        </p>
      </div>
    </section>
  )
}
