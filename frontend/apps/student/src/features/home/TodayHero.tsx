type TodayHeroProps = {
  studentName: string
  dateLabel: string
  title: string
  summary: string
}

export default function TodayHero({ studentName, dateLabel, title, summary }: TodayHeroProps) {
  return (
    <section className="grid gap-2">
      <div className="text-[12px] font-medium tracking-[0.08em] text-muted">{dateLabel}</div>
      <div className="grid gap-1">
        <h1 className="m-0 text-[clamp(28px,4vw,40px)] leading-[1.05] font-semibold text-ink">{title}</h1>
        <p className="m-0 max-w-[42rem] text-[14px] leading-[1.5] text-muted">
          {studentName ? `${studentName}，${summary}` : summary}
        </p>
      </div>
    </section>
  )
}
