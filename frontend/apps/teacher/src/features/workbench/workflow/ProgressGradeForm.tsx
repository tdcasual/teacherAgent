import type { FormEvent, ReactNode } from 'react';
import type { AssignmentProgressStudent } from '../../../appTypes';
import LabeledField from './LabeledField';

export type TeacherGradePayload = {
  override_score?: number | null;
  comment?: string;
  adopted_coach_excerpts?: Array<{ text: string }>;
  adopt_rubric_suggestion?: boolean;
  rubric_checks?: Array<{ id?: string; pass?: boolean; note?: string }>;
};

const parseAdoptedExcerpts = (raw: string): Array<{ text: string }> => {
  return raw
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((text) => ({ text }));
};

const submitStudentGrade = (
  event: FormEvent<HTMLFormElement>,
  studentId: string,
  saveStudentGrade: (studentId: string, payload: TeacherGradePayload) => Promise<void>,
) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const scoreRaw = String(form.get('override_score') || '').trim();
  const comment = String(form.get('comment') || '');
  const excerptsRaw = String(form.get('adopted_coach_excerpts') || '');
  const payload: TeacherGradePayload = {
    comment,
    adopted_coach_excerpts: parseAdoptedExcerpts(excerptsRaw),
  };
  if (scoreRaw) {
    const score = Number(scoreRaw);
    if (Number.isFinite(score)) payload.override_score = score;
  }
  void saveStudentGrade(studentId, payload);
};

export default function ProgressGradeForm({
  student,
  saveStudentGrade,
  progressLoading,
  children,
}: {
  student: AssignmentProgressStudent;
  saveStudentGrade: (studentId: string, payload: TeacherGradePayload) => Promise<void>;
  progressLoading: boolean;
  children?: ReactNode;
}) {
  return (
    <form
      className="mt-2 grid gap-1.5"
      onSubmit={(event) => submitStudentGrade(event, student.student_id, saveStudentGrade)}
    >
      <LabeledField label="覆盖分数">
        <input
          name="override_score"
          type="number"
          step="any"
          defaultValue={student.teacher_grade?.override_score_earned ?? ''}
        />
      </LabeledField>
      <LabeledField label="评语">
        <textarea name="comment" defaultValue={student.teacher_grade?.comment || ''} rows={2} />
      </LabeledField>
      <LabeledField label="采纳陪练摘录">
        <textarea
          name="adopted_coach_excerpts"
          placeholder="每行一条；未采纳的陪练评语不会记入成绩"
          defaultValue={(student.teacher_grade?.adopted_coach_excerpts || [])
            .map((item) => item.text || '')
            .filter(Boolean)
            .join('\n')}
          rows={2}
        />
      </LabeledField>
      <div className="flex flex-wrap gap-2">
        <button
          type="submit"
          className="border border-border rounded-xl py-[8px] px-[12px] bg-white text-ink cursor-pointer disabled:opacity-60"
          disabled={progressLoading}
        >
          保存成绩
        </button>
        <button
          type="button"
          className="border border-border rounded-xl py-[8px] px-[12px] bg-white text-ink cursor-pointer disabled:opacity-60"
          disabled={progressLoading}
          onClick={() => void saveStudentGrade(student.student_id, { override_score: null })}
        >
          恢复自动分
        </button>
        {children}
      </div>
    </form>
  );
}
