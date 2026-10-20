import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import AssignmentProgressSection from './AssignmentProgressSection';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const baseProps = {
  progressPanelCollapsed: false,
  setProgressPanelCollapsed: vi.fn(),
  formatProgressSummary: () => 'summary',
  progressAssignmentId: 'HW-1',
  setProgressAssignmentId: vi.fn(),
  progressOnlyIncomplete: false,
  setProgressOnlyIncomplete: vi.fn(),
  progressLoading: false,
  fetchAssignmentProgress: vi.fn(async () => undefined),
  progressError: '',
};

describe('AssignmentProgressSection', () => {
  it('renders result and process columns and colors by submitted not discussion', () => {
    render(
      <AssignmentProgressSection
        {...baseProps}
        progressData={{
          ok: true,
          assignment_id: 'HW-1',
          counts: { expected: 2, submitted: 1, completed: 1, overdue: 1, discussion_pass: 1 },
          students: [
            {
              student_id: 'S1',
              student_name: '张三',
              class_name: '高二1班',
              complete: true,
              overdue: false,
              discussion: { pass: false },
              submission: { attempts: 2, best: { score_earned: 8 } },
              official_score: 11,
              result: { attempts: 2, official_score: 11, overdue: false, submitted: true },
              process: { status: 'none', stuck_points: [], has_memory_proposal: false },
            },
            {
              student_id: 'S2',
              student_name: '李四',
              complete: false,
              overdue: true,
              discussion: { pass: true },
              submission: { attempts: 0 },
              official_score: null,
              result: { attempts: 0, official_score: null, overdue: true, submitted: false },
              process: {
                status: 'pending',
                stuck_points: [{ summary: '把 v 与 a 混用' }],
                has_memory_proposal: false,
              },
            },
          ],
        }}
      />,
    );

    expect(screen.getByText('结果')).toBeTruthy();
    expect(screen.getByText('过程')).toBeTruthy();
    expect(screen.getByText(/提交2次/)).toBeTruthy();
    expect(screen.getByText(/官方分11/)).toBeTruthy();
    expect(screen.getByText(/过程：无/)).toBeTruthy();
    expect(screen.getByText(/过程：生成中/)).toBeTruthy();
    expect(screen.queryByText('讨论通过')).toBeNull();
    expect(screen.queryByText('讨论未完成')).toBeNull();

    const submittedRow = screen.getByTestId('progress-row-S1');
    const discussionOnlyRow = screen.getByTestId('progress-row-S2');
    expect(submittedRow.className).toContain('bg-[color:var(--color-success-soft)]');
    expect(discussionOnlyRow.className).toContain('bg-[color:var(--color-danger-soft)]');
  });

  it('saves teacher grade override comment and adopted excerpts', () => {
    const saveStudentGrade = vi.fn(async () => undefined);
    render(
      <AssignmentProgressSection
        {...baseProps}
        saveStudentGrade={saveStudentGrade}
        progressData={{
          ok: true,
          assignment_id: 'HW-1',
          students: [
            {
              student_id: 'S1',
              complete: true,
              submission: { attempts: 1, best: { score_earned: 8 } },
              official_score: 8,
              result: { attempts: 1, official_score: 8, overdue: false, submitted: true },
              process: { status: 'none' },
            },
          ],
        }}
      />,
    );

    fireEvent.change(screen.getByLabelText('覆盖分数'), { target: { value: '12' } });
    fireEvent.change(screen.getByLabelText('评语'), { target: { value: '步骤完整' } });
    fireEvent.change(screen.getByLabelText('采纳陪练摘录'), { target: { value: '先写单位' } });
    fireEvent.click(screen.getByRole('button', { name: '保存成绩' }));

    expect(saveStudentGrade).toHaveBeenCalledWith('S1', {
      override_score: 12,
      comment: '步骤完整',
      adopted_coach_excerpts: [{ text: '先写单位' }],
    });
  });

  it('restores auto score by posting override_score null', () => {
    const saveStudentGrade = vi.fn(async () => undefined);
    render(
      <AssignmentProgressSection
        {...baseProps}
        saveStudentGrade={saveStudentGrade}
        progressData={{
          ok: true,
          assignment_id: 'HW-1',
          students: [
            {
              student_id: 'S1',
              complete: true,
              submission: { attempts: 1, best: { score_earned: 8 } },
              official_score: 12,
              teacher_grade: { override_score_earned: 12, comment: '覆盖' },
              result: { attempts: 1, official_score: 12, overdue: false, submitted: true },
              process: { status: 'none' },
            },
          ],
        }}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '恢复自动分' }));
    expect(saveStudentGrade).toHaveBeenCalledWith('S1', { override_score: null });
  });

  it('prompts teacher override when auto-grade left no official score', () => {
    const saveStudentGrade = vi.fn(async () => undefined);
    render(
      <AssignmentProgressSection
        {...baseProps}
        saveStudentGrade={saveStudentGrade}
        progressData={{
          ok: true,
          assignment_id: 'HW-1',
          students: [
            {
              student_id: 'S1',
              complete: false,
              submission: { attempts: 1 },
              official_score: null,
              result: { attempts: 1, official_score: null, overdue: false, submitted: false },
              process: { status: 'none' },
            },
          ],
        }}
      />,
    );

    expect(screen.getByText('未自动出分，请老师覆盖')).toBeTruthy();
    expect(screen.getByRole('button', { name: '保存成绩' })).toBeTruthy();
  });

  it('shows practice counts for problem_set and 不适用 for other kinds', () => {
    const { rerender } = render(
      <AssignmentProgressSection
        {...baseProps}
        progressData={{
          ok: true,
          assignment_id: 'HW-1',
          assignment_kind: 'problem_set',
          students: [
            {
              student_id: 'S1',
              complete: true,
              submission: { attempts: 1 },
              official_score: 8,
              result: { attempts: 1, official_score: 8, overdue: false, submitted: true },
              process: { status: 'none' },
              practice: { assigned: 1, submitted: 0, open: 1, bank_miss: true },
            },
          ],
        }}
      />,
    );

    expect(screen.getByText('补练')).toBeTruthy();
    expect(screen.getByTestId('progress-practice-S1').textContent).toContain('已布置1');
    expect(screen.getByTestId('progress-practice-S1').textContent).toContain('已交0');
    expect(screen.getByTestId('progress-practice-S1').textContent).toContain('题库不足');
    expect(screen.getByText(/提交1次/)).toBeTruthy();

    rerender(
      <AssignmentProgressSection
        {...baseProps}
        progressData={{
          ok: true,
          assignment_id: 'HW-2',
          assignment_kind: 'practical',
          students: [
            {
              student_id: 'S1',
              complete: true,
              submission: { attempts: 1 },
              official_score: null,
              result: { attempts: 1, official_score: null, overdue: false, submitted: true },
              process: { status: 'none' },
              practice: { assigned: 0, submitted: 0, open: 0, bank_miss: false },
            },
          ],
        }}
      />,
    );
    expect(screen.getByTestId('progress-practice-S1').textContent).toContain('不适用');
  });

  it('does not paint 官方分0 when photo received_without_items keeps score_earned null', () => {
    render(
      <AssignmentProgressSection
        {...baseProps}
        progressData={{
          ok: true,
          assignment_id: 'HW-PHOTO',
          assignment_kind: 'practical',
          students: [
            {
              student_id: 'S1',
              complete: false,
              submission: {
                attempts: 1,
                best: { score_earned: null, received_without_items: true },
              },
              official_score: null,
              result: { attempts: 1, official_score: null, overdue: false, submitted: true },
              process: { status: 'none' },
            },
          ],
        }}
      />,
    );

    expect(screen.getByText(/无官方分/)).toBeTruthy();
    expect(screen.queryByText(/官方分0/)).toBeNull();
    expect(screen.getByText('未自动出分，请老师覆盖')).toBeTruthy();
  });

  it('posts merged adopted_coach_excerpts when adopting an excerpt', () => {
    const saveStudentGrade = vi.fn(async () => undefined);
    render(
      <AssignmentProgressSection
        {...baseProps}
        saveStudentGrade={saveStudentGrade}
        progressData={{
          ok: true,
          assignment_id: 'HW-1',
          assignment_kind: 'scenario',
          students: [
            {
              student_id: 'S1',
              complete: true,
              submission: { attempts: 1 },
              official_score: null,
              result: { attempts: 1, official_score: null, overdue: false, submitted: true },
              process: { status: 'frozen' },
              process_archive_status: 'frozen',
              process_archive: {
                status: 'frozen',
                quotes: [{ text: '学生原话', speaker: 'student' }],
                coach_comment_excerpts: [{ text: '新条目' }],
              },
              teacher_grade: { adopted_coach_excerpts: [{ text: '旧条目' }] },
            },
          ],
        }}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '采纳为评语' }));
    expect(saveStudentGrade).toHaveBeenCalledWith('S1', {
      adopted_coach_excerpts: [{ text: '旧条目' }, { text: '新条目' }],
    });
  });

  it('hides adopt-rubric button without a suggested score and shows it when scored', () => {
    const saveStudentGrade = vi.fn(async () => undefined);
    const { rerender } = render(
      <AssignmentProgressSection
        {...baseProps}
        saveStudentGrade={saveStudentGrade}
        progressData={{
          ok: true,
          assignment_id: 'HW-1',
          assignment_kind: 'scenario',
          rubric: { source: 'rubric.md', items: [{ id: '1', text: '能指出情景约束' }] },
          students: [
            {
              student_id: 'S1',
              complete: true,
              submission: { attempts: 1 },
              official_score: null,
              result: { attempts: 1, official_score: null, overdue: false, submitted: true },
              process: { status: 'none' },
              rubric_suggestion: { status: 'ready', suggested_score: null, source: 'heuristic_none' },
            },
          ],
        }}
      />,
    );

    expect(screen.getByTestId('progress-assignment-rubric').textContent).toContain(
      '能指出情景约束',
    );
    expect(screen.queryByTestId('progress-adopt-rubric-S1')).toBeNull();
    expect(screen.getByText('请按量规目测后手填覆盖')).toBeTruthy();

    rerender(
      <AssignmentProgressSection
        {...baseProps}
        saveStudentGrade={saveStudentGrade}
        progressData={{
          ok: true,
          assignment_id: 'HW-1',
          assignment_kind: 'scenario',
          rubric: { source: 'none', items: [] },
          students: [
            {
              student_id: 'S1',
              complete: true,
              submission: { attempts: 1 },
              official_score: null,
              result: { attempts: 1, official_score: null, overdue: false, submitted: true },
              process: { status: 'none' },
              rubric_suggestion: { status: 'ready', suggested_score: 12, comment: '建议评语' },
            },
          ],
        }}
      />,
    );
    expect(screen.getByText('无量规，请老师覆盖')).toBeTruthy();
    fireEvent.click(screen.getByTestId('progress-adopt-rubric-S1'));
    expect(saveStudentGrade).toHaveBeenCalledWith('S1', { adopt_rubric_suggestion: true });
  });

  it('does not show assignment rubric for problem_set', () => {
    render(
      <AssignmentProgressSection
        {...baseProps}
        progressData={{
          ok: true,
          assignment_id: 'HW-1',
          assignment_kind: 'problem_set',
          rubric: { source: 'rubric.md', items: [{ id: '1', text: '不该出现' }] },
          students: [
            {
              student_id: 'S1',
              complete: true,
              submission: { attempts: 1 },
              official_score: 8,
              result: { attempts: 1, official_score: 8, overdue: false, submitted: true },
              process: { status: 'none' },
              practice: { assigned: 1, submitted: 0, open: 1, bank_miss: false },
            },
          ],
        }}
      />,
    );
    expect(screen.queryByTestId('progress-assignment-rubric')).toBeNull();
    expect(screen.queryByTestId('progress-adopt-rubric-S1')).toBeNull();
  });

  it('renders teacher portrait snippet from full profile fields', () => {
    render(
      <AssignmentProgressSection
        {...baseProps}
        progressData={{
          ok: true,
          assignment_id: 'HW-1',
          assignment_kind: 'scenario',
          students: [
            {
              student_id: 'S1',
              complete: true,
              submission: { attempts: 1 },
              official_score: null,
              result: { attempts: 1, official_score: null, overdue: false, submitted: true },
              process: { status: 'none' },
              portrait: {
                recent_weak_kp: ['受力分析'],
                next_focus: '牛顿定律',
                last_source: 'graded',
              },
            },
            {
              student_id: 'S2',
              complete: false,
              submission: { attempts: 0 },
              official_score: null,
              result: { attempts: 0, official_score: null, overdue: false, submitted: false },
              process: { status: 'none' },
              portrait: { recent_weak_kp: [], next_focus: '', last_source: '' },
            },
          ],
        }}
      />,
    );
    expect(screen.getByTestId('progress-portrait-S1').textContent).toContain('薄弱：受力分析');
    expect(screen.getByTestId('progress-portrait-S1').textContent).toContain('下一步：牛顿定律');
    expect(screen.getByTestId('progress-portrait-S1').textContent).toContain('最近：graded');
    expect(screen.getByTestId('progress-portrait-S2').textContent).toContain('薄弱：暂无');
  });
});
