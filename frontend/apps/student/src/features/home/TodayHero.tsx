type TodayHeroProps = {
  dateLabel: string;
};

export default function TodayHero({ dateLabel }: TodayHeroProps) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-2">
      <h1 className="m-0 text-[clamp(20px,5vw,28px)] font-semibold tracking-[-0.02em] text-ink">
        今日任务
      </h1>
      <span className="text-[12px] font-medium text-muted">{dateLabel}</span>
    </div>
  );
}
