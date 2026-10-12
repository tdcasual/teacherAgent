import { useEffect, useMemo, useState } from 'react';

import type { StudentAssignmentHistoryItem } from '../../appTypes';
import { coerceAssignmentKind } from '../../assignmentKind';

type StudentPortraitCardProps = {
  apiBase: string;
  studentId: string;
  items?: StudentAssignmentHistoryItem[];
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

const latestPracticeFromHistory = (history: unknown[]): string => {
  for (let index = history.length - 1; index >= 0; index -= 1) {
    const entry = history[index];
    if (!entry || typeof entry !== 'object') continue;
    const record = asRecord(entry);
    const practiceId = String(record.practice_id || '').trim();
    if (!practiceId) continue;
    const assignmentId = String(record.assignment_id || '').trim();
    return [assignmentId, practiceId].filter(Boolean).join(' · ');
  }
  return '';
};

const outcomeLine = (item: StudentAssignmentHistoryItem): string => {
  const kind = coerceAssignmentKind(item.assignment_kind);
  const submittedLabel = item.submitted ? '已提交' : '未提交';
  let scoreLabel = '—';
  if (item.submitted) {
    scoreLabel = item.official_score == null ? '已交未评分' : String(item.official_score);
  }
  return `${kind} · ${submittedLabel} · ${scoreLabel}`;
};

const parsePortrait = (payload: unknown): PortraitModel => {
  const record = asRecord(payload);
  const history = Array.isArray(record.practice_history) ? record.practice_history : [];
  return {
    recentWeakKp: asStringList(record.recent_weak_kp),
    nextFocus: String(record.next_focus || '').trim(),
    latestPracticeLabel: latestPracticeFromHistory(history),
  };
};

export default function StudentPortraitCard({
  apiBase,
  studentId,
  items = [],
}: StudentPortraitCardProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [portrait, setPortrait] = useState<PortraitModel | null>(null);
  const outcomeLines = useMemo(() => items.slice(0, 5).map(outcomeLine), [items]);

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
      <dl className="m-0 grid gap-1 text-[13px]">
        <div>
          <dt className="text-[12px] text-muted">近期薄弱知识点</dt>
          <dd className="m-0" data-testid="student-portrait-recent-weak-kp">
            {portrait?.recentWeakKp.length ? portrait.recentWeakKp.join('、') : '暂无'}
          </dd>
        </div>
        <div>
          <dt className="text-[12px] text-muted">下一步</dt>
          <dd className="m-0" data-testid="student-portrait-next-focus">
            {portrait?.nextFocus || '暂无'}
          </dd>
        </div>
        <div>
          <dt className="text-[12px] text-muted">最近作业</dt>
          <dd className="m-0" data-testid="student-portrait-recent-outcomes">
            {outcomeLines.length ? (
              <ul className="m-0 grid list-none gap-1 p-0">
                {outcomeLines.map((line, index) => (
                  <li key={`${line}-${index}`}>{line}</li>
                ))}
              </ul>
            ) : (
              '暂无'
            )}
          </dd>
        </div>
        <div>
          <dt className="text-[12px] text-muted">最近补练</dt>
          <dd className="m-0" data-testid="student-portrait-practice-history">
            {portrait?.latestPracticeLabel || '暂无'}
          </dd>
        </div>
      </dl>
    </section>
  );
}
