import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import * as teacherAuth from '../auth/teacherAuth';
import AdminSchoolPanel from './AdminSchoolPanel';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function mockAdminFetch() {
  vi.spyOn(teacherAuth, 'readTeacherAccessToken').mockReturnValue('admin-token');
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = String(init?.method || 'GET').toUpperCase();
    if (url.includes('/auth/admin/teacher/list')) {
      return {
        ok: true,
        json: async () => ({
          ok: true,
          items: [{ teacher_id: 't_zhang01', teacher_name: '张老师' }],
        }),
      };
    }
    if (url.includes('/auth/admin/subjects')) {
      return {
        ok: true,
        json: async () => ({ ok: true, items: [{ subject_id: 'physics', display_name: '物理' }] }),
      };
    }
    if (url.includes('/auth/admin/assignments/orphans')) {
      return {
        ok: true,
        json: async () => ({
          ok: true,
          items: [{ assignment_id: 'HW_ORPHAN', subject_id: '', teacher_id: '' }],
        }),
      };
    }
    if (url.includes('/auth/admin/teacher/create')) {
      return {
        ok: true,
        json: async () => ({
          ok: true,
          teacher_id: 't_zhang',
          temp_password: 'TempPass12ab',
          teacher: { teacher_id: 't_zhang', teacher_name: '张老师' },
        }),
      };
    }
    if (url.includes('/auth/admin/students/import')) {
      expect(method).toBe('POST');
      expect(init?.body).toBeInstanceOf(FormData);
      return {
        ok: true,
        json: async () => ({
          ok: true,
          created: 1,
          updated: 0,
          items: [
            {
              student_id: 's_zhang',
              student_name: '张三',
              class_name: '高二1班',
              temp_password: 'StuPass12ab',
              created: true,
            },
          ],
        }),
      };
    }
    if (url.includes('/auth/admin/roster') && method === 'POST') {
      return { ok: true, json: async () => ({ ok: true }) };
    }
    if (url.includes('/auth/admin/enrollments/enroll-class')) {
      return { ok: true, json: async () => ({ ok: true }) };
    }
    if (url.includes('/auth/admin/assignments/HW_ORPHAN/claim')) {
      return { ok: true, json: async () => ({ ok: true }) };
    }
    throw new Error(`unexpected url ${url}`);
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

describe('AdminSchoolPanel', () => {
  it('creates a teacher and shows temp password as a copy-once text node', async () => {
    mockAdminFetch();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });

    render(<AdminSchoolPanel />);

    expect(
      document.querySelector('[class*="min-w-[720px]"]') ||
        screen.getByRole('region', { name: '学校管理' }),
    ).toBeTruthy();
    fireEvent.change(screen.getByLabelText('教师姓名'), { target: { value: '张老师' } });
    fireEvent.click(screen.getByRole('button', { name: '创建教师' }));

    const passwordNode = await screen.findByText('TempPass12ab');
    expect(passwordNode.tagName).not.toBe('INPUT');
    expect(passwordNode.getAttribute('value')).toBeNull();
    expect(passwordNode.getAttribute('data-password')).toBeNull();

    const copyButton = screen.getByRole('button', { name: '复制一次' });
    fireEvent.click(copyButton);
    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith('TempPass12ab');
      expect(screen.queryByRole('button', { name: '复制一次' })).toBeNull();
    });
  });

  it('imports roster CSV without auto-enrolling, then enrolls via roster and enroll-class', async () => {
    const fetchMock = mockAdminFetch();
    render(<AdminSchoolPanel />);

    await screen.findByRole('option', { name: '张老师' });
    const file = new File(['student_name,class_name\n张三,高二1班\n'], 'roster.csv', {
      type: 'text/csv',
    });
    fireEvent.change(screen.getByLabelText('名册 CSV'), { target: { files: [file] } });
    fireEvent.click(screen.getByRole('button', { name: '导入名册' }));

    expect(await screen.findByText('StuPass12ab')).toBeTruthy();
    expect(
      fetchMock.mock.calls.some((call) => String(call[0]).includes('/auth/admin/students/import')),
    ).toBe(true);
    expect(fetchMock.mock.calls.some((call) => String(call[0]).includes('/enroll-class'))).toBe(
      false,
    );

    fireEvent.change(screen.getByLabelText('班级'), { target: { value: '高二1班' } });
    fireEvent.click(screen.getByRole('button', { name: '加任教' }));
    await screen.findByText('已加任教。');
    fireEvent.click(screen.getByRole('button', { name: '整班入学' }));
    await screen.findByText('已整班入学。');

    const posted = fetchMock.mock.calls.map(
      (call) => `${String(call[1]?.method || 'GET').toUpperCase()} ${String(call[0])}`,
    );
    expect(
      posted.some((item) => item.includes('POST') && item.includes('/auth/admin/roster')),
    ).toBe(true);
    expect(
      posted.some(
        (item) => item.includes('POST') && item.includes('/auth/admin/enrollments/enroll-class'),
      ),
    ).toBe(true);
  });

  it('claims an orphan assignment for the selected teacher and subject', async () => {
    const fetchMock = mockAdminFetch();
    render(<AdminSchoolPanel />);

    await screen.findByRole('option', { name: '张老师' });
    fireEvent.click(await screen.findByRole('button', { name: '认领给当前教师' }));
    await screen.findByText('已认领 HW_ORPHAN。');
    expect(
      fetchMock.mock.calls.some((call) =>
        String(call[0]).includes('/auth/admin/assignments/HW_ORPHAN/claim'),
      ),
    ).toBe(true);
  });
});
