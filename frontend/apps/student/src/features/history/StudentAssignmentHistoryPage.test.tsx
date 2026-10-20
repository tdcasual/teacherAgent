import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { StudentAssignmentHistoryItem } from '../../appTypes';
import StudentAssignmentHistoryPage from './StudentAssignmentHistoryPage';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

const items: StudentAssignmentHistoryItem[] = [
  {
    assignment_id: 'HW_DONE',
    teacher_id: 't_zhang',
    subject_id: 'physics',
    title: '已交力学',
    due_at: '2026-08-20T23:59:59',
    visibility_status: 'published',
    submitted: true,
    official_score: 12,
    archived_at: null,
    assignment_kind: 'problem_set',
    allow_practice: true,
    practice: { bank_miss: false },
  },
  {
    assignment_id: 'HW_OPEN',
    teacher_id: 't_zhang',
    subject_id: 'physics',
    title: '未交力学',
    due_at: '2026-08-29T23:59:59',
    visibility_status: 'published',
    submitted: false,
    official_score: null,
    archived_at: null,
    assignment_kind: 'problem_set',
    allow_practice: true,
    practice: { bank_miss: false },
  },
  {
    assignment_id: 'HW_ARCHIVED',
    teacher_id: 't_zhang',
    subject_id: 'math',
    title: '归档未交',
    due_at: '',
    visibility_status: 'archived',
    submitted: false,
    official_score: null,
    archived_at: '2026-08-25T00:00:00',
    assignment_kind: 'problem_set',
    allow_practice: true,
    practice: { bank_miss: false },
  },
];

const stubProfileFetch = () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (String(url).includes('/student/profile/')) {
        return new Response(
          JSON.stringify({
            recent_weak_kp: ['牛顿第二定律'],
            next_focus: '受力分析',
            practice_history: [{ assignment_id: 'HW_DONE', status: 'completed' }],
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        );
      }
      return new Response(JSON.stringify({ ok: true, practice_id: 'practice_1' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }),
  );
};

describe('StudentAssignmentHistoryPage', () => {
  it('lists assignment history and shows official scores for submitted work', async () => {
    stubProfileFetch();
    render(
      <StudentAssignmentHistoryPage
        items={items}
        loading={false}
        error=""
        apiBase="http://localhost:8000"
        studentId="S1"
        onBack={() => undefined}
        onSubmit={() => undefined}
        onOpenAssignment={() => undefined}
      />,
    );

    expect(screen.getByTestId('student-assignment-history-page')).toBeTruthy();
    expect(screen.getByText('作业记录')).toBeTruthy();
    expect(screen.getByText('已交力学')).toBeTruthy();
    expect(screen.getByText('官方分 12')).toBeTruthy();
    expect(screen.getByText('未交力学')).toBeTruthy();
    expect(screen.getByText('归档未交')).toBeTruthy();
    await waitFor(() => expect(screen.getByTestId('student-portrait-card')).toBeTruthy());
  });

  it('lets published unsubmitted work open the submit panel, not session history', () => {
    stubProfileFetch();
    const onSubmit = vi.fn();
    const onOpenAssignment = vi.fn();
    const onBack = vi.fn();
    render(
      <StudentAssignmentHistoryPage
        items={items}
        loading={false}
        error=""
        apiBase="http://localhost:8000"
        studentId="S1"
        onBack={onBack}
        onSubmit={onSubmit}
        onOpenAssignment={onOpenAssignment}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '补交 未交力学' }));
    expect(onSubmit).toHaveBeenCalledWith('HW_OPEN');
    expect(onOpenAssignment).not.toHaveBeenCalled();
    expect(onBack).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: '补交 归档未交' })).toBeNull();
  });

  it('shows 补练 only for submitted problem_set with allow_practice and surfaces bank_miss', async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (String(url).includes('/student/profile/')) {
        return new Response(
          JSON.stringify({ recent_weak_kp: [], next_focus: '', practice_history: [] }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        );
      }
      expect(init?.method).toBe('POST');
      return new Response(JSON.stringify({ detail: 'question_bank_insufficient' }), {
        status: 409,
        headers: { 'Content-Type': 'application/json' },
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    render(
      <StudentAssignmentHistoryPage
        items={[
          items[0],
          {
            ...items[1],
            assignment_id: 'HW_SCENARIO',
            title: '情景作业',
            submitted: true,
            official_score: null,
            assignment_kind: 'scenario',
            allow_practice: false,
          },
          {
            assignment_id: 'HW_NO_PRACTICE',
            teacher_id: 't_zhang',
            subject_id: 'physics',
            title: '关闭补练',
            visibility_status: 'published',
            submitted: true,
            official_score: 8,
            assignment_kind: 'problem_set',
            allow_practice: false,
            practice: { bank_miss: false },
          },
          {
            assignment_id: 'HW_BANK_MISS',
            teacher_id: 't_zhang',
            subject_id: 'physics',
            title: '空库补练',
            visibility_status: 'published',
            submitted: true,
            official_score: 7,
            assignment_kind: 'problem_set',
            allow_practice: true,
            practice: { bank_miss: true },
          },
        ]}
        loading={false}
        error=""
        apiBase="http://localhost:8000"
        studentId="S1"
        onBack={() => undefined}
        onSubmit={() => undefined}
        onOpenAssignment={() => undefined}
      />,
    );

    expect(screen.getByTestId('student-practice-start-HW_DONE')).toBeTruthy();
    expect(screen.getByTestId('student-practice-start-HW_BANK_MISS')).toBeTruthy();
    expect(screen.queryByTestId('student-practice-start-HW_SCENARIO')).toBeNull();
    expect(screen.queryByTestId('student-practice-start-HW_NO_PRACTICE')).toBeNull();
    expect(screen.queryByTestId('student-practice-start-HW_OPEN')).toBeNull();
    expect(screen.getByTestId('student-practice-bank-miss').textContent).toContain('题库不足');
    expect(screen.getByTestId('student-portrait-card')).toBeTruthy();

    fireEvent.click(screen.getByTestId('student-practice-start-HW_DONE'));
    await waitFor(() => {
      const calls = fetchMock.mock.calls;
      const lastCall = calls[calls.length - 1];
      expect(String(lastCall?.[0])).toBe(
        'http://localhost:8000/student/assignment/HW_DONE/practice',
      );
    });
    await waitFor(() => expect(screen.getAllByText('题库不足').length).toBeGreaterThan(0));
  });
});
