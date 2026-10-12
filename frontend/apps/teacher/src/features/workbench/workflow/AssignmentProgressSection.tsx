import type { Dispatch, FormEvent, SetStateAction } from 'react';
import type { AssignmentProgress, AssignmentProgressStudent } from '../../../appTypes';
import type { FormatProgressSummary } from '../../../types/workflow';
import LabeledField from './LabeledField';

export type TeacherGradePayload = {
  override_score?: number | null;
  comment?: string;
  adopted_coach_excerpts?: Array<{ text: string }>;
  adopt_rubric_suggestion?: boolean;
  rubric_checks?: Array<{ id?: string; pass?: boolean; note?: string }>;
};

type AssignmentProgressSectionProps = {
  progressPanelCollapsed: boolean;
  setProgressPanelCollapsed: Dispatch<SetStateAction<boolean>>;
  formatProgressSummary: FormatProgressSummary;
  progressData: AssignmentProgress | null;
  progressAssignmentId: string;
  setProgressAssignmentId: (value: string) => void;
  progressOnlyIncomplete: boolean;
  setProgressOnlyIncomplete: (value: boolean) => void;
  progressLoading: boolean;
  fetchAssignmentProgress: (assignmentId?: string) => Promise<void>;
  progressError: string;
  archiveAssignment?: (assignmentId?: string) => Promise<void>;
  unarchiveAssignment?: (assignmentId?: string) => Promise<void>;
  saveStudentGrade?: (studentId: string, payload: TeacherGradePayload) => Promise<void>;
};

const extractBestScore = (value: unknown): number | null => {
  if (!value || typeof value !== 'object') return null;
  const candidate = value as { score_earned?: unknown };
  const score = Number(candidate.score_earned);
  return Number.isFinite(score) ? score : null;
};

const processStatusLabel = (status?: string) => {
  if (status === 'pending') return '生成中';
  if (status === 'frozen') return '已冻结';
  if (status === 'partial') return '部分';
  return '无';
};

const officialScoreOf = (student: AssignmentProgressStudent): number | null => {
  if (typeof student.result?.official_score === 'number') return student.result.official_score;
  if (typeof student.official_score === 'number') return student.official_score;
  return extractBestScore(student.submission?.best);
};

const practiceColumnLabel = (student: AssignmentProgressStudent, applicable: boolean): string => {
  if (!applicable) return '不适用';
  const assigned = Number(student.practice?.assigned || 0);
  const submitted = Number(student.practice?.submitted || 0);
  const bankMiss = Boolean(student.practice?.bank_miss);
  return `已布置${assigned} · 已交${submitted}${bankMiss ? ' · 题库不足' : ''}`;
};

const parseAdoptedExcerpts = (raw: string): Array<{ text: string }> => {
  return raw
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((text) => ({ text }));
};

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

const portraitLabel = (student: AssignmentProgressStudent): string => {
  const weak = (student.portrait?.recent_weak_kp || []).map((item) => String(item || '').trim()).filter(Boolean);
  const next = String(student.portrait?.next_focus || '').trim();
  const source = String(student.portrait?.last_source || '').trim();
  return `薄弱：${weak.length ? weak.join('、') : '暂无'} · 下一步：${next || '暂无'} · 最近：${source || '暂无'}`;
};

const canAdoptRubric = (student: AssignmentProgressStudent): boolean => {
  const suggestion = student.rubric_suggestion;
  if (suggestion?.status !== 'ready' || suggestion?.suggested_score == null) return false;
  return Number.isFinite(Number(suggestion.suggested_score));
};

const examNotesBody = (
  student: AssignmentProgressStudent,
  saveStudentGrade?: (studentId: string, payload: TeacherGradePayload) => Promise<void>,
) => {
  const archive = student.process_archive;
  const status = String(student.process_archive_status || archive?.status || 'none');
  if (!archive || status === 'none') return '无陪练纪要';
  if (status === 'pending') return '生成中';
  return (
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
};

const submitStudentGrade = (
  event: FormEvent<HTMLFormElement>,
  studentId: string,
  saveStudentGrade?: (studentId: string, payload: TeacherGradePayload) => Promise<void>,
) => {
  event.preventDefault();
  if (!saveStudentGrade) return;
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

export default function AssignmentProgressSection(props: AssignmentProgressSectionProps) {
  const {
    progressPanelCollapsed,
    setProgressPanelCollapsed,
    formatProgressSummary,
    progressData,
    progressAssignmentId,
    setProgressAssignmentId,
    progressOnlyIncomplete,
    setProgressOnlyIncomplete,
    progressLoading,
    fetchAssignmentProgress,
    progressError,
    archiveAssignment,
    unarchiveAssignment,
    saveStudentGrade,
  } = props;
  const visibilityStatus = String(progressData?.visibility_status || '').trim();
  const showPractice = progressData?.assignment_kind === 'problem_set';
  const showRubric = Boolean(
    progressData?.assignment_kind && progressData.assignment_kind !== 'problem_set',
  );

  return (
    <section
      id="workflow-progress-section"
      data-testid="workflow-progress-section"
      className={`mt-3 bg-surface border border-border rounded-[14px] shadow-sm ${progressPanelCollapsed ? 'py-[10px] px-3' : 'p-[10px]'}`}
    >
      <div
        className={`flex items-start gap-2 flex-wrap ${progressPanelCollapsed ? 'mb-0' : 'mb-2'}`}
      >
        <h3 className="m-0 whitespace-nowrap shrink-0">作业完成情况</h3>
        {progressPanelCollapsed ? (
          <div
            className="flex-1 min-w-0 text-muted text-[12px] whitespace-nowrap overflow-hidden text-ellipsis"
            title={formatProgressSummary(progressData, progressAssignmentId)}
          >
            {formatProgressSummary(progressData, progressAssignmentId)}
          </div>
        ) : null}
        <button
          type="button"
          className="ghost"
          onClick={() => setProgressPanelCollapsed((v: boolean) => !v)}
        >
          {progressPanelCollapsed ? '展开' : '收起'}
        </button>
      </div>
      {progressPanelCollapsed ? null : (
        <>
          <div className="flex items-end justify-between gap-3 flex-wrap mb-[10px]">
            <LabeledField label="作业编号" className="grid gap-1.5 min-w-[240px]">
              <input
                value={progressAssignmentId}
                onChange={(e) => setProgressAssignmentId(e.target.value)}
                placeholder="例如：A2403_2026-02-04"
              />
            </LabeledField>
            <div className="flex items-center gap-3 flex-wrap">
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={progressOnlyIncomplete}
                  onChange={(e) => setProgressOnlyIncomplete(e.target.checked)}
                />
                只看未完成
              </label>
              <button
                type="button"
                data-testid="progress-refresh"
                className="border border-border rounded-xl py-[10px] px-[14px] bg-white text-ink cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
                disabled={progressLoading}
                onClick={() => void fetchAssignmentProgress()}
              >
                {progressLoading ? '加载中…' : '刷新'}
              </button>
              {visibilityStatus === 'archived' ? (
                <button
                  type="button"
                  className="border border-border rounded-xl py-[10px] px-[14px] bg-white text-ink cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
                  disabled={progressLoading || !unarchiveAssignment}
                  onClick={() => void unarchiveAssignment?.()}
                >
                  取消归档
                </button>
              ) : (
                <button
                  type="button"
                  className="border border-border rounded-xl py-[10px] px-[14px] bg-white text-ink cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
                  disabled={progressLoading || !archiveAssignment}
                  onClick={() => void archiveAssignment?.()}
                >
                  归档
                </button>
              )}
            </div>
          </div>

          {progressError && (
            <div className="mt-[10px] p-[10px_12px] rounded-xl text-[12px] whitespace-pre-wrap overflow-x-auto bg-danger-soft text-danger">
              {progressError}
            </div>
          )}
          {progressData && (
            <div className="text-[13px] text-muted grid gap-1">
              <div>作业编号：{progressData.assignment_id}</div>
              <div>日期：{String(progressData.date || '') || '（未设置）'}</div>
              <div>
                应交：{progressData.counts?.expected ?? progressData.expected_count ?? 0} · 已提交：
                {progressData.counts?.submitted ?? 0} · 完成：
                {progressData.counts?.completed ?? 0}
                {progressData.counts?.overdue ? ` · 逾期：${progressData.counts.overdue}` : ''}
              </div>
              <div>截止：{progressData.due_at ? progressData.due_at : '永不截止'}</div>
              <div className="flex gap-6">
                <span>结果</span>
                <span>过程</span>
                <span>补练</span>
              </div>
              {showRubric ? (
                <div data-testid="progress-assignment-rubric" className="mt-1">
                  {progressData?.rubric?.source === 'rubric.md' &&
                  (progressData.rubric.items || []).length > 0 ? (
                    <ul className="m-0 pl-4">
                      {(progressData.rubric.items || []).map((item) => (
                        <li key={item.id || item.text}>{item.text}</li>
                      ))}
                    </ul>
                  ) : (
                    <div>无量规，请老师覆盖</div>
                  )}
                </div>
              ) : null}
            </div>
          )}

          {progressData?.students && progressData.students.length > 0 && (
            <div className="mt-3 grid gap-2">
              {(progressOnlyIncomplete
                ? progressData.students.filter((s: AssignmentProgressStudent) => !s.complete)
                : progressData.students
              ).map((s: AssignmentProgressStudent) => {
                const attempts = s.result?.attempts ?? s.submission?.attempts ?? 0;
                const official = officialScoreOf(s);
                const overdue = Boolean(s.result?.overdue ?? s.overdue);
                const processStatus = s.process?.status || 'none';
                const liveStuck = String(s.process?.stuck_points?.[0]?.summary || '').trim();
                const archiveStuck = (s.process_archive?.stuck_points || [])
                  .map((item) => String(item?.summary || '').trim())
                  .filter(Boolean)
                  .slice(0, 2)
                  .join('；');
                const stuckNote = liveStuck || archiveStuck;
                const processNote = stuckNote ? ` · ${stuckNote}` : '';
                const name = [s.class_name, s.student_name].filter(Boolean).join(' ');
                const archiveStatus = String(
                  s.process_archive_status || s.process_archive?.status || 'none',
                );
                const processLabel =
                  archiveStatus === 'none' || !archiveStatus ? '无' : archiveStatus;
                const memory = s.has_memory_proposal ? ' · 有记忆提案' : '';
                return (
                  <div
                    key={s.student_id}
                    data-testid={`progress-row-${s.student_id}`}
                    className={`progress-row border rounded-[14px] py-[10px] px-3 flex justify-between gap-3 items-start ${s.complete ? 'border-[color:var(--color-success)] bg-[color:var(--color-success-soft)]' : 'border-[color:var(--color-danger)] bg-[color:var(--color-danger-soft)]'}`}
                  >
                    <div className="text-[13px] min-w-0 flex-1">
                      <strong>{s.student_id}</strong>
                      {name ? <span className="text-muted text-[12px]"> {name}</span> : null}
                      <div className="grid grid-cols-3 gap-2 mt-1 text-[12px] text-muted">
                        <div>
                          提交{attempts}次 · {official != null ? `官方分${official}` : '无官方分'}
                          {overdue ? ' · 逾期' : ''}
                        </div>
                        <div>
                          过程：{processStatusLabel(processStatus) || processLabel}
                          {processNote}
                          {memory}
                        </div>
                        <div data-testid={`progress-practice-${s.student_id}`}>
                          {practiceColumnLabel(s, showPractice)}
                        </div>
                      </div>
                      {attempts > 0 && official == null ? (
                        <div className="text-[12px] text-muted mt-1">未自动出分，请老师覆盖</div>
                      ) : null}
                      <div
                        className="text-[12px] text-muted mt-1"
                        data-testid={`progress-portrait-${s.student_id}`}
                      >
                        {portraitLabel(s)}
                      </div>
                      <details
                        className="mt-1 text-[12px] text-muted"
                        data-testid={`progress-exam-notes-${s.student_id}`}
                      >
                        <summary>考查纪要</summary>
                        {examNotesBody(s, saveStudentGrade)}
                      </details>
                      {showRubric && !canAdoptRubric(s) ? (
                        <div className="text-[12px] text-muted mt-1">请按量规目测后手填覆盖</div>
                      ) : null}
                      {saveStudentGrade ? (
                        <form
                          className="mt-2 grid gap-1.5"
                          onSubmit={(event) =>
                            submitStudentGrade(event, s.student_id, saveStudentGrade)
                          }
                        >
                          <LabeledField label="覆盖分数">
                            <input
                              name="override_score"
                              type="number"
                              step="any"
                              defaultValue={s.teacher_grade?.override_score_earned ?? ''}
                            />
                          </LabeledField>
                          <LabeledField label="评语">
                            <textarea
                              name="comment"
                              defaultValue={s.teacher_grade?.comment || ''}
                              rows={2}
                            />
                          </LabeledField>
                          <LabeledField label="采纳陪练摘录">
                            <textarea
                              name="adopted_coach_excerpts"
                              placeholder="每行一条；未采纳的陪练评语不会记入成绩"
                              defaultValue={(s.teacher_grade?.adopted_coach_excerpts || [])
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
                              onClick={() =>
                                void saveStudentGrade(s.student_id, { override_score: null })
                              }
                            >
                              恢复自动分
                            </button>
                            {showRubric && canAdoptRubric(s) ? (
                              <button
                                type="button"
                                data-testid={`progress-adopt-rubric-${s.student_id}`}
                                className="border border-border rounded-xl py-[8px] px-[12px] bg-white text-ink cursor-pointer disabled:opacity-60"
                                disabled={progressLoading}
                                onClick={() =>
                                  void saveStudentGrade(s.student_id, {
                                    adopt_rubric_suggestion: true,
                                  })
                                }
                              >
                                按量规给分
                              </button>
                            ) : null}
                          </div>
                        </form>
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </section>
  );
}
