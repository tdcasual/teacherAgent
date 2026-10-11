import { useEffect, useState } from 'react';

type StudentPortraitCardProps = {
  apiBase: string;
  studentId: string;
};

type PortraitModel = {
  recentWeakKp: string[];
  nextFocus: string;
  latestPracticeLabel: string;
};

const asRecord = (value: unknown): Record<string, unknown> =>
  value && typeof value === 'object' ? (value as Record<string, unknown>) : {};

const asStringList = (value: unknown): string[] => {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item || '').trim()).filter(Boolean);
};

const parsePortrait = (payload: unknown): PortraitModel => {
  const record = asRecord(payload);
  const history = Array.isArray(record.practice_history) ? record.practice_history : [];
  const first = history[0] && typeof history[0] === 'object' ? asRecord(history[0]) : null;
  const latestPracticeLabel = first
    ? [String(first.assignment_id || '').trim(), String(first.status || '').trim()]
        .filter(Boolean)
        .join(' · ')
    : '';
  return {
    recentWeakKp: asStringList(record.recent_weak_kp),
    nextFocus: String(record.next_focus || '').trim(),
    latestPracticeLabel,
  };
};

export default function StudentPortraitCard({ apiBase, studentId }: StudentPortraitCardProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [portrait, setPortrait] = useState<PortraitModel | null>(null);

  useEffect(() => {
    const sid = studentId.trim();
    if (!sid) {
      setPortrait(null);
      setError('');
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setError('');
    void (async () => {
      try {
        const res = await fetch(`${apiBase}/student/profile/${encodeURIComponent(sid)}`, {
          signal: controller.signal,
        });
        if (res.status === 404) {
          setPortrait({ recentWeakKp: [], nextFocus: '', latestPracticeLabel: '' });
          return;
        }
        if (!res.ok) {
          throw new Error(`状态码 ${res.status}`);
        }
        const data = await res.json();
        setPortrait(parsePortrait(data));
      } catch {
        if (controller.signal.aborted) return;
        setError('暂无画像');
        setPortrait(null);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    })();
    return () => controller.abort();
  }, [apiBase, studentId]);

  if (!studentId.trim()) return null;

  return (
    <section
      className="grid gap-2 rounded-[16px] border border-border bg-white px-4 py-3"
      data-testid="student-portrait-card"
    >
      <h2 className="m-0 text-[15px] font-medium text-ink">学习画像</h2>
      {loading ? <div className="text-[12px] text-muted">加载中…</div> : null}
      {error ? <div className="text-[12px] text-muted">{error}</div> : null}
      {portrait ? (
        <dl className="m-0 grid gap-1 text-[13px]">
          <div>
            <dt className="text-[12px] text-muted">近期薄弱知识点</dt>
            <dd className="m-0" data-testid="student-portrait-recent-weak-kp">
              {portrait.recentWeakKp.length ? portrait.recentWeakKp.join('、') : '暂无'}
            </dd>
          </div>
          <div>
            <dt className="text-[12px] text-muted">下一步</dt>
            <dd className="m-0" data-testid="student-portrait-next-focus">
              {portrait.nextFocus || '暂无'}
            </dd>
          </div>
          <div>
            <dt className="text-[12px] text-muted">最近练习</dt>
            <dd className="m-0" data-testid="student-portrait-practice-history">
              {portrait.latestPracticeLabel || '暂无'}
            </dd>
          </div>
        </dl>
      ) : null}
    </section>
  );
}
