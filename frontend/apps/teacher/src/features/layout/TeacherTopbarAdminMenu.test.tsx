import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createRef } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import * as teacherAuth from '../auth/teacherAuth';
import TeacherTopbarAdminMenu from './TeacherTopbarAdminMenu';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('TeacherTopbarAdminMenu password reset scope', () => {
  it('hides reset-all for non-admin teachers', () => {
    vi.spyOn(teacherAuth, 'readTeacherAccessToken').mockReturnValue('teacher-token');
    vi.spyOn(teacherAuth, 'readTeacherAuthRole').mockReturnValue('teacher');
    vi.spyOn(teacherAuth, 'readTeacherAuthSubject').mockReturnValue({
      teacher_id: 'T001',
      teacher_name: '张老师',
    });

    render(
      <TeacherTopbarAdminMenu
        open
        panelRef={createRef<HTMLDivElement>()}
        authed
        authSubjectLabel="张老师"
        onOpenModelSettingsPanel={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText('按学生或班级重置密码。')).toBeTruthy();
    expect(screen.queryByRole('button', { name: '全部学生' })).toBeNull();
  });

  it('shows reset-all only for admin', () => {
    vi.spyOn(teacherAuth, 'readTeacherAccessToken').mockReturnValue('admin-token');
    vi.spyOn(teacherAuth, 'readTeacherAuthRole').mockReturnValue('admin');
    vi.spyOn(teacherAuth, 'readTeacherAuthSubject').mockReturnValue({
      teacher_id: 'admin',
      teacher_name: '校长',
      role: 'admin',
    });

    render(
      <TeacherTopbarAdminMenu
        open
        panelRef={createRef<HTMLDivElement>()}
        authed
        authSubjectLabel="校长"
        onOpenModelSettingsPanel={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText('按学生、班级或全部学生重置密码。')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '全部学生' }));
    expect(screen.getByText('我确认重置全部学生密码')).toBeTruthy();
  });

  it('logs admin in via POST /auth/admin/login and stores role=admin', async () => {
    const writeSession = vi
      .spyOn(teacherAuth, 'writeTeacherAuthSession')
      .mockImplementation(() => undefined);
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      expect(url).toContain('/auth/admin/login');
      expect(url).not.toContain('/auth/teacher/');
      return {
        ok: true,
        json: async () => ({
          ok: true,
          access_token: 'admin-access',
          role: 'admin',
          subject_id: 'principal_admin',
        }),
      };
    });
    vi.stubGlobal('fetch', fetchMock);
    const onClose = vi.fn();

    render(
      <TeacherTopbarAdminMenu
        open
        panelRef={createRef<HTMLDivElement>()}
        authed={false}
        authSubjectLabel=""
        onOpenModelSettingsPanel={vi.fn()}
        onClose={onClose}
      />,
    );

    fireEvent.change(screen.getByLabelText('管理员用户名'), {
      target: { value: 'principal_admin' },
    });
    fireEvent.change(screen.getByLabelText('管理员密码'), { target: { value: 'AdminPass1' } });
    fireEvent.click(screen.getByRole('button', { name: '管理员登录' }));

    await waitFor(() => {
      expect(writeSession).toHaveBeenCalledWith({
        accessToken: 'admin-access',
        teacherId: 'principal_admin',
        teacherName: 'principal_admin',
        role: 'admin',
      });
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toEqual({
      username: 'principal_admin',
      password: 'AdminPass1',
    });
    expect(onClose).toHaveBeenCalled();
  });

  it('persists access_token after set-password and does not claim old token still works', async () => {
    const writeSession = vi
      .spyOn(teacherAuth, 'writeTeacherAuthSession')
      .mockImplementation(() => undefined);
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/auth/teacher/identify')) {
        return {
          ok: true,
          json: async () => ({ ok: true, candidate_id: 'cid_teacher' }),
        };
      }
      if (url.includes('/auth/teacher/set-password')) {
        return {
          ok: true,
          json: async () => ({
            ok: true,
            access_token: 'new-access',
            role: 'teacher',
            subject_id: 'teacher_alpha',
            teacher: { teacher_id: 'teacher_alpha', teacher_name: '张老师' },
          }),
        };
      }
      throw new Error(`unexpected ${url}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    render(
      <TeacherTopbarAdminMenu
        open
        panelRef={createRef<HTMLDivElement>()}
        authed={false}
        authSubjectLabel=""
        onOpenModelSettingsPanel={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText('姓名'), { target: { value: '张老师' } });
    fireEvent.change(screen.getByLabelText('token'), { target: { value: 'issued-token' } });
    fireEvent.change(screen.getByLabelText('新密码'), { target: { value: 'NewPass12' } });
    fireEvent.click(screen.getByRole('button', { name: '设置密码' }));

    await waitFor(() => {
      expect(writeSession).toHaveBeenCalledWith({
        accessToken: 'new-access',
        teacherId: 'teacher_alpha',
        teacherName: '张老师',
        role: 'teacher',
      });
    });
    expect(screen.getByText('密码设置成功，后续可使用密码登录。')).toBeTruthy();
    expect(screen.queryByText(/token 仍可用/)).toBeNull();
  });

  it('accent CTAs use text-on-accent instead of text-white', () => {
    const { rerender } = render(
      <TeacherTopbarAdminMenu
        open
        panelRef={createRef<HTMLDivElement>()}
        authed={false}
        authSubjectLabel=""
        onOpenModelSettingsPanel={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    const unauthNames = ['管理员登录', '确认认证', '设置密码'];
    for (const name of unauthNames) {
      const className = screen.getByRole('button', { name }).className;
      expect(className).toContain('text-on-accent');
      expect(className).not.toContain('text-white');
    }

    vi.spyOn(teacherAuth, 'readTeacherAccessToken').mockReturnValue('teacher-token');
    vi.spyOn(teacherAuth, 'readTeacherAuthRole').mockReturnValue('teacher');
    rerender(
      <TeacherTopbarAdminMenu
        open
        panelRef={createRef<HTMLDivElement>()}
        authed
        authSubjectLabel="张老师"
        onOpenModelSettingsPanel={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    const resetClassName = screen.getByRole('button', { name: '重置学生密码' }).className;
    expect(resetClassName).toContain('text-on-accent');
    expect(resetClassName).not.toContain('text-white');
  });
});
