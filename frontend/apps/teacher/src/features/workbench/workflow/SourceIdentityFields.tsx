import type { SourceIdentityFieldsProps } from '../../../types/workflow';
import LabeledField from './LabeledField';

const ASSIGNMENT_SUBJECT_OPTIONS = [
  { id: 'physics', label: '物理' },
  { id: 'math', label: '数学' },
  { id: 'generic', label: '通用' },
] as const;

export default function SourceIdentityFields(props: SourceIdentityFieldsProps) {
  const {
    assignmentId,
    setAssignmentId,
    date,
    setDate,
    dueAt,
    setDueAt,
    subjectId,
    setSubjectId,
    className,
    setClassName,
    studentIds,
    setStudentIds,
    assignmentIdTestId,
  } = props;
  const subjectIds = ASSIGNMENT_SUBJECT_OPTIONS.map((option) => option.id);
  const merged = subjectIds.includes(subjectId as (typeof subjectIds)[number])
    ? subjectIds
    : [subjectId, ...subjectIds];

  return (
    <div className="grid gap-[10px] grid-cols-1">
      <LabeledField label="作业编号">
        <input
          data-testid={assignmentIdTestId}
          value={assignmentId}
          onChange={(e) => setAssignmentId(e.target.value)}
          placeholder="例如：HW-2026-02-05"
        />
      </LabeledField>
      <LabeledField label="日期（可选）">
        <input value={date} onChange={(e) => setDate(e.target.value)} placeholder="YYYY-MM-DD" />
      </LabeledField>
      <LabeledField label="截止日期（可选）">
        <input
          value={dueAt}
          onChange={(e) => setDueAt(e.target.value)}
          placeholder="YYYY-MM-DD 或 ISO 时间"
        />
      </LabeledField>
      <LabeledField label="学科">
        <select value={subjectId} onChange={(e) => setSubjectId(e.target.value)}>
          {merged.map((id) => (
            <option key={id} value={id}>
              {ASSIGNMENT_SUBJECT_OPTIONS.find((option) => option.id === id)?.label || id}
            </option>
          ))}
        </select>
      </LabeledField>
      <LabeledField label="班级（可选）">
        <input
          value={className}
          onChange={(e) => setClassName(e.target.value)}
          placeholder="例如：高二2403班"
        />
      </LabeledField>
      <LabeledField label="学生编号（可选）">
        <input
          value={studentIds}
          onChange={(e) => setStudentIds(e.target.value)}
          placeholder="例如：高二2403班_刘昊然"
        />
      </LabeledField>
    </div>
  );
}
