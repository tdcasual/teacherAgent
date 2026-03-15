type TodayHeroProps = {
  dateLabel: string
}

export default function TodayHero({ dateLabel }: TodayHeroProps) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-[12px] font-medium text-muted">
      <span>{dateLabel}</span>
    </div>
  )
}
