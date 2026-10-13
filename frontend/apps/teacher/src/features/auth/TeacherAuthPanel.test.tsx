import { readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import * as teacherAuth from './teacherAuth';
import TeacherAuthPanel from './TeacherAuthPanel';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

const walkTsFiles = (dir: string, acc: string[] = []): string[] => {
  for (const name of readdirSync(dir)) {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) walkTsFiles(full, acc);
    else if (/\.(ts|tsx)$/.test(name)) acc.push(full);
  }
  return acc;
};

describe('TeacherAuthPanel', () => {
  it('writeTeacherAuthSession only appears in teacherAuth definition, AuthPanel, and tests', () => {
    const appsRoot = path.resolve(process.cwd(), 'apps');
    const hits = walkTsFiles(appsRoot)
      .filter((file) => readFileSync(file, 'utf8').includes('writeTeacherAuthSession'))
      .map((file) => path.relative(appsRoot, file).replace(/\\/g, '/'))
      .sort();
    expect(hits).toEqual([
      'teacher/src/features/auth/TeacherAuthPanel.test.tsx',
      'teacher/src/features/auth/TeacherAuthPanel.tsx',
      'teacher/src/features/auth/teacherAuth.ts',
      'teacher/src/features/layout/TeacherTopbarAdminMenu.test.tsx',
    ]);
  });

  it('persists admin login with role=admin', async () => {
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

    render(<TeacherAuthPanel authed={false} onClose={onClose} />);
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
    expect(onClose).toHaveBeenCalled();
  });

  it('persists teacher login session', async () => {
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
      if (url.includes('/auth/teacher/login')) {
        return {
          ok: true,
          json: async () => ({
            ok: true,
            access_token: 'teacher-access',
            role: 'teacher',
            subject_id: 'teacher_alpha',
            teacher: { teacher_id: 'teacher_alpha', teacher_name: '张老师' },
          }),
        };
      }
      throw new Error(`unexpected ${url}`);
    });
    vi.stubGlobal('fetch', fetchMock);
    const onClose = vi.fn();

    render(<TeacherAuthPanel authed={false} onClose={onClose} />);
    fireEvent.change(screen.getByLabelText('姓名'), { target: { value: '张老师' } });
    fireEvent.change(screen.getByLabelText('token'), { target: { value: 'issued-token' } });
    fireEvent.click(screen.getByRole('button', { name: '确认认证' }));

    await waitFor(() => {
      expect(writeSession).toHaveBeenCalledWith({
        accessToken: 'teacher-access',
        teacherId: 'teacher_alpha',
        teacherName: '张老师',
        role: 'teacher',
      });
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

    render(<TeacherAuthPanel authed={false} onClose={vi.fn()} />);
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

  it('does not persist when set-password succeeds without access_token', async () => {
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
            role: 'teacher',
            subject_id: 'teacher_alpha',
            teacher: { teacher_id: 'teacher_alpha', teacher_name: '张老师' },
          }),
        };
      }
      throw new Error(`unexpected ${url}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<TeacherAuthPanel authed={false} onClose={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('姓名'), { target: { value: '张老师' } });
    fireEvent.change(screen.getByLabelText('token'), { target: { value: 'issued-token' } });
    fireEvent.change(screen.getByLabelText('新密码'), { target: { value: 'NewPass12' } });
    fireEvent.click(screen.getByRole('button', { name: '设置密码' }));

    await waitFor(() => {
      expect(screen.getByText('密码设置成功，后续可使用密码登录。')).toBeTruthy();
    });
    expect(writeSession).not.toHaveBeenCalled();
    expect(screen.queryByText(/token 仍可用/)).toBeNull();
  });
});
