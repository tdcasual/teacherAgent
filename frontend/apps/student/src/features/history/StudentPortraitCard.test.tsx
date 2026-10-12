import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { StudentAssignmentHistoryItem } from '../../appTypes';
import StudentPortraitCard from './StudentPortraitCard';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

const historyItem = (
  overrides: Partial<StudentAssignmentHistoryItem> & { assignment_id: string },
): StudentAssignmentHistoryItem => ({
  teacher_id: 't_zhang',
  subject_id: 'physics',
  title: overrides.assignment_id,
  due_at: '',
  visibility_status: 'published',
  submitted: false,
  official_score: null,
  archived_at: null,
  assignment_kind: 'problem_set',
  allow_practice: true,
  ...overrides,
});

describe('StudentPortraitCard', () => {
  it('reads recent_weak_kp next_focus and last practice_id and never weak_kp', async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            student_id: 'S1',
            recent_weak_kp: ['牛顿第二定律'],
            weak_kp: ['hidden-legacy-kp'],
            next_focus: '受力分析',
            practice_history: [
              { assignment_id: 'OLD' },
              { assignment_id: 'NEW', practice_id: 'practice_ab' },
            ],
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
    );
    vi.stubGlobal('fetch', fetchMock);

    const items: StudentAssignmentHistoryItem[] = [
      historyItem({
        assignment_id: 'HW_NEW',
        assignment_kind: 'problem_set',
        submitted: true,
        official_score: 12,
      }),
      historyItem({
        assignment_id: 'HW_SCENARIO',
        assignment_kind: 'scenario',
        submitted: true,
        official_score: null,
      }),
      historyItem({
        assignment_id: 'HW_OPEN',
        assignment_kind: 'practical',
        submitted: false,
        official_score: null,
      }),
      historyItem({ assignment_id: 'HW_4', submitted: true, official_score: 8 }),
      historyItem({ assignment_id: 'HW_5', submitted: true, official_score: 7 }),
      historyItem({ assignment_id: 'HW_6', submitted: true, official_score: 6 }),
    ];

    render(<StudentPortraitCard apiBase="http://localhost:8000" studentId="S1" items={items} />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe('http://localhost:8000/student/profile/S1');
    expect(screen.getByTestId('student-portrait-recent-weak-kp').textContent).toContain(
      '牛顿第二定律',
    );
    expect(screen.getByTestId('student-portrait-next-focus').textContent).toContain('受力分析');
    const practice = screen.getByTestId('student-portrait-practice-history').textContent || '';
    expect(practice).toContain('NEW');
    expect(practice).toContain('practice_ab');
    expect(practice).not.toContain('OLD');
    expect(screen.queryByText('hidden-legacy-kp')).toBeNull();
    const outcomes = screen.getByTestId('student-portrait-recent-outcomes').textContent || '';
    expect(outcomes).toContain('problem_set · 已提交 · 12');
    expect(outcomes).toContain('scenario · 已提交 · 已交未评分');
    expect(outcomes).toContain('practical · 未提交 · —');
    expect(outcomes).not.toContain('HW_6');
  });

  it('does not label homework brief_fallback rows as 最近补练', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              practice_history: [{ assignment_id: 'HW_HOMEWORK', source: 'brief_fallback' }],
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          ),
      ),
    );

    render(<StudentPortraitCard apiBase="http://localhost:8000" studentId="S1" items={[]} />);

    await waitFor(() =>
      expect(screen.getByTestId('student-portrait-practice-history').textContent).toContain('暂无'),
    );
    expect(screen.getByTestId('student-portrait-practice-history').textContent).not.toContain(
      'HW_HOMEWORK',
    );
  });
});
