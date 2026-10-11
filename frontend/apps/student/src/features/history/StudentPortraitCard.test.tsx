import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import StudentPortraitCard from './StudentPortraitCard';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('StudentPortraitCard', () => {
  it('reads recent_weak_kp next_focus and practice_history[0] and never weak_kp', async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            student_id: 'S1',
            recent_weak_kp: ['牛顿第二定律'],
            weak_kp: ['hidden-legacy-kp'],
            next_focus: '受力分析',
            practice_history: [{ assignment_id: 'HW_DONE', status: 'completed' }],
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
    );
    vi.stubGlobal('fetch', fetchMock);

    render(<StudentPortraitCard apiBase="http://localhost:8000" studentId="S1" />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe('http://localhost:8000/student/profile/S1');
    expect(screen.getByTestId('student-portrait-recent-weak-kp').textContent).toContain(
      '牛顿第二定律',
    );
    expect(screen.getByTestId('student-portrait-next-focus').textContent).toContain('受力分析');
    expect(screen.getByTestId('student-portrait-practice-history').textContent).toContain(
      'HW_DONE',
    );
    expect(screen.queryByText('hidden-legacy-kp')).toBeNull();
  });
});
