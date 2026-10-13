import type { AssignmentProgress, AssignmentProgressStudent } from '../../../appTypes';

export const canAdoptRubric = (student: AssignmentProgressStudent): boolean => {
  const suggestion = student.rubric_suggestion;
  if (suggestion?.status !== 'ready' || suggestion?.suggested_score == null) return false;
  return Number.isFinite(Number(suggestion.suggested_score));
};

export function ProgressAdoptRubricButton({
  student,
  saveStudentGrade,
  disabled,
}: {
  student: AssignmentProgressStudent;
  saveStudentGrade: (
    studentId: string,
    payload: { adopt_rubric_suggestion: true },
  ) => Promise<void>;
  disabled?: boolean;
}) {
  if (!canAdoptRubric(student)) return null;
  return (
    <button
      type="button"
      data-testid={`progress-adopt-rubric-${student.student_id}`}
      className="border border-border rounded-xl py-[8px] px-[12px] bg-white text-ink cursor-pointer disabled:opacity-60"
      disabled={disabled}
      onClick={() =>
        void saveStudentGrade(student.student_id, {
          adopt_rubric_suggestion: true,
        })
      }
    >
      按量规给分
    </button>
  );
}

export default function ProgressRubricBlock({ rubric }: { rubric?: AssignmentProgress['rubric'] }) {
  return (
    <div data-testid="progress-assignment-rubric" className="mt-1">
      {rubric?.source === 'rubric.md' && (rubric.items || []).length > 0 ? (
        <ul className="m-0 pl-4">
          {(rubric.items || []).map((item) => (
            <li key={item.id || item.text}>{item.text}</li>
          ))}
        </ul>
      ) : (
        <div>无量规，请老师覆盖</div>
      )}
    </div>
  );
}
