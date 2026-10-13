import type { AssignmentProgressStudent } from '../../../appTypes';

const portraitLabel = (student: AssignmentProgressStudent): string => {
  const weak = (student.portrait?.recent_weak_kp || [])
    .map((item) => String(item || '').trim())
    .filter(Boolean);
  const next = String(student.portrait?.next_focus || '').trim();
  const source = String(student.portrait?.last_source || '').trim();
  return `薄弱：${weak.length ? weak.join('、') : '暂无'} · 下一步：${next || '暂无'} · 最近：${source || '暂无'}`;
};

export default function ProgressPortraitSnippet({
  student,
}: {
  student: AssignmentProgressStudent;
}) {
  return (
    <div
      className="text-[12px] text-muted mt-1"
      data-testid={`progress-portrait-${student.student_id}`}
    >
      {portraitLabel(student)}
    </div>
  );
}
