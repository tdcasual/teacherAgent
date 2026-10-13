import type { ReactNode } from 'react';
import type { AssignmentProgressStudent } from '../../../appTypes';
import type { TeacherGradePayload } from './ProgressGradeForm';

const mergeAdoptedExcerpts = (
  existing: Array<{ text?: string }> | undefined,
  nextText: string,
): Array<{ text: string }> => {
  const merged = (existing || [])
    .map((item) => ({ text: String(item?.text || '').trim() }))
    .filter((item) => item.text);
  const text = nextText.trim();
  if (text && !merged.some((item) => item.text === text)) merged.push({ text });
  return merged;
};

export default function ProgressExamNotes({
  student,
  saveStudentGrade,
}: {
  student: AssignmentProgressStudent;
  saveStudentGrade?: (studentId: string, payload: TeacherGradePayload) => Promise<void>;
}) {
  const archive = student.process_archive;
  const status = String(student.process_archive_status || archive?.status || 'none');
  let body: ReactNode = '无陪练纪要';
  if (archive && status !== 'none') {
    if (status === 'pending') {
      body = '生成中';
    } else {
      body = (
        <div className="grid gap-1">
          {(archive.quotes || []).map((quote, index) => (
            <div key={`q-${index}`}>
              {quote.speaker === 'coach' ? '陪练' : '学生'}：{quote.text}
            </div>
          ))}
          {(archive.coach_comment_excerpts || []).map((excerpt, index) => {
            const text = String(excerpt.text || '').trim();
            if (!text) return null;
            return (
              <div key={`e-${index}`} className="flex flex-wrap items-start gap-2">
                <span>摘录：{text}</span>
                {saveStudentGrade ? (
                  <button
                    type="button"
                    className="border border-border rounded-xl py-[4px] px-[8px] bg-white text-ink cursor-pointer"
                    onClick={() =>
                      // HTTP adopted_coach_excerpts is whole-array replace; merge so adopt does not wipe old rows.
                      void saveStudentGrade(student.student_id, {
                        adopted_coach_excerpts: mergeAdoptedExcerpts(
                          student.teacher_grade?.adopted_coach_excerpts,
                          text,
                        ),
                      })
                    }
                  >
                    采纳为评语
                  </button>
                ) : null}
              </div>
            );
          })}
        </div>
      );
    }
  }

  return (
    <details
      className="mt-1 text-[12px] text-muted"
      data-testid={`progress-exam-notes-${student.student_id}`}
    >
      <summary>考查纪要</summary>
      {body}
    </details>
  );
}
