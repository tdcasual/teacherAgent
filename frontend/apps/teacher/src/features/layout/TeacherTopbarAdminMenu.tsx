import { useId, useState, type FormEvent, type MutableRefObject } from 'react';

import { resolveRuntimeApiBase } from '../../../../shared/apiBase';
import { safeLocalStorageGetItem } from '../../utils/storage';
import {
  clearTeacherAuthSession,
  readTeacherAccessToken,
  readTeacherAuthRole,
  writeTeacherAuthSession,
} from '../auth/teacherAuth';
import TeacherAdminPanel from './TeacherAdminPanel';

type TeacherTopbarAdminMenuProps = {
  open: boolean;
  panelRef: MutableRefObject<HTMLDivElement | null>;
  authed: boolean;
  authSubjectLabel: string;
  onOpenModelSettingsPanel: () => void;
  onClose: () => void;
};

type TeacherIdentifyResponse = {
  ok: boolean;
  error?: string;
  message?: string;
  candidate_id?: string;
  need_email_disambiguation?: boolean;
};

type StudentIdentifyResponse = {
  ok: boolean;
  error?: string;
  message?: string;
  candidate_id?: string;
};

type TeacherLoginResponse = {
  ok: boolean;
  error?: string;
  message?: string;
  access_token?: string;
  subject_id?: string;
  role?: string;
  teacher?: {
    teacher_id?: string;
    teacher_name?: string;
    email?: string;
  };
};

type TeacherSetPasswordResponse = {
  ok: boolean;
  error?: string;
  message?: string;
};

type StudentPasswordResetScope = 'student' | 'class' | 'all';

type StudentPasswordResetItem = {
  student_id?: string;
  student_name?: string;
  class_name?: string;
  temp_password?: string;
};

type TeacherStudentPasswordResetResponse = {
  ok: boolean;
  error?: string;
  message?: string;
  count?: number;
  items?: StudentPasswordResetItem[];
};

const toText = (value: unknown): string => String(value ?? '').trim();

const mapStudentResetError = (errorCode: string, fallback: string): string => {
  if (errorCode === 'missing_student_id') return '请先填写学生姓名和班级。';
  if (errorCode === 'missing_class_name') return '请先填写班级名称。';
  if (errorCode === 'not_found') return '未找到匹配学生，请检查输入条件。';
  if (errorCode === 'weak_password') return '密码至少 8 位，且需同时包含字母与数字。';
  if (errorCode === 'forbidden') return '当前账号没有执行该操作的权限。';
  return fallback;
};

const buildStudentPasswordRows = (items: StudentPasswordResetItem[]): string =>
  items
    .map((item) =>
      [
        toText(item.student_id),
        toText(item.student_name),
        toText(item.class_name),
        toText(item.temp_password),
      ].join(','),
    )
    .join('\n');

export default function TeacherTopbarAdminMenu({
  open,
  panelRef,
  authed,
  authSubjectLabel,
  onOpenModelSettingsPanel,
  onClose,
}: TeacherTopbarAdminMenuProps) {
  const [nameInput, setNameInput] = useState('');
  const [emailInput, setEmailInput] = useState('');
  const [credentialInput, setCredentialInput] = useState('');
  const [credentialType, setCredentialType] = useState<'token' | 'password'>('token');
  const [newPasswordInput, setNewPasswordInput] = useState('');
  const [needEmail, setNeedEmail] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [settingPassword, setSettingPassword] = useState(false);
  const [authError, setAuthError] = useState('');
  const [authInfo, setAuthInfo] = useState('');

  const [studentResetScope, setStudentResetScope] = useState<StudentPasswordResetScope>('student');
  const [studentNameInput, setStudentNameInput] = useState('');
  const [studentClassInput, setStudentClassInput] = useState('');
  const [targetClassNameInput, setTargetClassNameInput] = useState('');
  const [studentResetPasswordInput, setStudentResetPasswordInput] = useState('');
  const [confirmResetAll, setConfirmResetAll] = useState(false);
  const [studentResetSubmitting, setStudentResetSubmitting] = useState(false);
  const [studentResetError, setStudentResetError] = useState('');
  const [studentResetInfo, setStudentResetInfo] = useState('');
  const [studentResetItems, setStudentResetItems] = useState<StudentPasswordResetItem[]>([]);
  const [adminUsernameInput, setAdminUsernameInput] = useState('');
  const [adminPasswordInput, setAdminPasswordInput] = useState('');
  const [adminSubmitting, setAdminSubmitting] = useState(false);
  const formId = useId();
  const adminUsernameInputId = `${formId}-admin-username`;
  const adminPasswordInputId = `${formId}-admin-password`;
  const nameInputId = `${formId}-name`;
  const emailInputId = `${formId}-email`;
  const credentialInputId = `${formId}-credential`;
  const newPasswordInputId = `${formId}-new-password`;
  const studentNameInputId = `${formId}-student-name`;
  const studentClassInputId = `${formId}-student-class`;
  const targetClassInputId = `${formId}-target-class`;
  const studentResetPasswordInputId = `${formId}-student-reset-password`;
  const confirmResetAllId = `${formId}-confirm-reset-all`;
  const isAdmin = readTeacherAuthRole() === 'admin';

  const handleAdminLogin = async (event: FormEvent) => {
    event.preventDefault();
    const apiBase = resolveRuntimeApiBase(safeLocalStorageGetItem('apiBaseTeacher'));
    const username = adminUsernameInput.trim();
    const password = adminPasswordInput.trim();
    setAuthError('');
    setAuthInfo('');
    if (!username) {
      setAuthError('请输入管理员用户名。');
      return;
    }
    if (!password) {
      setAuthError('请输入管理员密码。');
      return;
    }
    setAdminSubmitting(true);
    try {
      const loginRes = await fetch(`${apiBase}/auth/admin/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      if (!loginRes.ok) {
        const text = await loginRes.text();
        throw new Error(text || `状态码 ${loginRes.status}`);
      }
      const loginData = (await loginRes.json()) as TeacherLoginResponse;
      if (!loginData.ok || !loginData.access_token) {
        const reason = toText(loginData.error);
        let message = loginData.message || '管理员认证失败。';
        if (reason === 'invalid_credential') message = '管理员用户名或密码不正确。';
        else if (reason === 'locked') message = '尝试次数过多，请稍后再试。';
        setAuthError(message);
        return;
      }
      const subjectId = toText(loginData.subject_id) || username;
      writeTeacherAuthSession({
        accessToken: loginData.access_token,
        teacherId: subjectId,
        teacherName: username,
        role: toText(loginData.role) || 'admin',
      });
      setAdminPasswordInput('');
      setAuthInfo('管理员认证成功。');
      onClose();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error || '管理员认证失败');
      setAuthError(message);
    } finally {
      setAdminSubmitting(false);
    }
  };

  const handleAuthSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const apiBase = resolveRuntimeApiBase(safeLocalStorageGetItem('apiBaseTeacher'));
    const name = nameInput.trim();
    const email = emailInput.trim();
    const credential = credentialInput.trim();

    setAuthError('');
    setAuthInfo('');

    if (!name) {
      setAuthError('请输入教师姓名。');
      return;
    }
    if (!credential) {
      setAuthError(credentialType === 'token' ? '请输入 token。' : '请输入密码。');
      return;
    }

    setSubmitting(true);
    try {
      const identifyRes = await fetch(`${apiBase}/auth/teacher/identify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email: email || undefined }),
      });
      if (!identifyRes.ok) {
        const text = await identifyRes.text();
        throw new Error(text || `状态码 ${identifyRes.status}`);
      }
      const identifyData = (await identifyRes.json()) as TeacherIdentifyResponse;
      if (!identifyData.ok || !identifyData.candidate_id) {
        const needEmailFlag = Boolean(identifyData.need_email_disambiguation);
        setNeedEmail(needEmailFlag);
        setAuthError(
          identifyData.message ||
            (needEmailFlag ? '该姓名存在多个教师，请补充邮箱。' : '未找到该教师。'),
        );
        return;
      }

      const loginRes = await fetch(`${apiBase}/auth/teacher/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          candidate_id: identifyData.candidate_id,
          credential_type: credentialType,
          credential,
        }),
      });
      if (!loginRes.ok) {
        const text = await loginRes.text();
        throw new Error(text || `状态码 ${loginRes.status}`);
      }
      const loginData = (await loginRes.json()) as TeacherLoginResponse;
      if (!loginData.ok || !loginData.access_token) {
        const reason = toText(loginData.error);
        let message = loginData.message || '教师认证失败。';
        if (reason === 'invalid_credential') {
          message = credentialType === 'token' ? 'token 不正确，请重试。' : '密码不正确，请重试。';
        } else if (reason === 'password_not_set') {
          message = '当前教师账号尚未设置密码，请先使用 token 登录。';
        } else if (reason === 'locked') {
          message = '尝试次数过多，请稍后再试。';
        }
        setAuthError(message);
        return;
      }

      const teacher = loginData.teacher || {};
      const teacherId = toText(
        loginData.subject_id || teacher.teacher_id || identifyData.candidate_id,
      );
      const teacherName = toText(teacher.teacher_name || name || teacherId);
      const teacherEmail = toText(teacher.email || email);
      writeTeacherAuthSession({
        accessToken: loginData.access_token,
        teacherId,
        teacherName,
        role: toText(loginData.role) || 'teacher',
        ...(teacherEmail ? { email: teacherEmail } : {}),
      });

      setNeedEmail(false);
      setCredentialInput('');
      setAuthInfo('认证成功。');
      onClose();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error || '认证失败');
      setAuthError(message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleSetPassword = async (event: FormEvent) => {
    event.preventDefault();
    const apiBase = resolveRuntimeApiBase(safeLocalStorageGetItem('apiBaseTeacher'));
    const name = nameInput.trim();
    const email = emailInput.trim();
    const credential = credentialInput.trim();
    const newPassword = newPasswordInput.trim();

    setAuthError('');
    setAuthInfo('');

    if (!name) {
      setAuthError('请输入教师姓名。');
      return;
    }
    if (!credential) {
      setAuthError('请先输入用于校验的 token 或当前密码。');
      return;
    }
    if (!newPassword) {
      setAuthError('请输入新密码。');
      return;
    }

    setSettingPassword(true);
    try {
      const identifyRes = await fetch(`${apiBase}/auth/teacher/identify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email: email || undefined }),
      });
      if (!identifyRes.ok) {
        const text = await identifyRes.text();
        throw new Error(text || `状态码 ${identifyRes.status}`);
      }
      const identifyData = (await identifyRes.json()) as TeacherIdentifyResponse;
      if (!identifyData.ok || !identifyData.candidate_id) {
        const needEmailFlag = Boolean(identifyData.need_email_disambiguation);
        setNeedEmail(needEmailFlag);
        setAuthError(
          identifyData.message ||
            (needEmailFlag ? '该姓名存在多个教师，请补充邮箱。' : '未找到该教师。'),
        );
        return;
      }

      const setPasswordRes = await fetch(`${apiBase}/auth/teacher/set-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          candidate_id: identifyData.candidate_id,
          credential_type: credentialType,
          credential,
          new_password: newPassword,
        }),
      });
      if (!setPasswordRes.ok) {
        const text = await setPasswordRes.text();
        throw new Error(text || `状态码 ${setPasswordRes.status}`);
      }
      const setPasswordData = (await setPasswordRes.json()) as TeacherSetPasswordResponse;
      if (!setPasswordData.ok) {
        const reason = toText(setPasswordData.error);
        let message = setPasswordData.message || '设置密码失败。';
        if (reason === 'weak_password') {
          message = '密码至少 8 位，且需同时包含字母和数字。';
        } else if (reason === 'invalid_credential') {
          message = '当前 token/密码校验失败，请重试。';
        }
        setAuthError(message);
        return;
      }

      setCredentialType('password');
      setNewPasswordInput('');
      setAuthInfo('密码设置成功，后续可使用密码登录（token 仍可用）。');
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error || '设置密码失败');
      setAuthError(message);
    } finally {
      setSettingPassword(false);
    }
  };

  const handleStudentPasswordReset = async (event: FormEvent) => {
    event.preventDefault();
    const apiBase = resolveRuntimeApiBase(safeLocalStorageGetItem('apiBaseTeacher'));
    const accessToken = readTeacherAccessToken();
    if (!accessToken) {
      setStudentResetError('请先完成教师认证。');
      return;
    }

    setStudentResetError('');
    setStudentResetInfo('');
    setStudentResetItems([]);
    setStudentResetSubmitting(true);
    try {
      const payload: Record<string, string> = { scope: studentResetScope };
      const requestedPassword = studentResetPasswordInput.trim();
      if (requestedPassword) payload.new_password = requestedPassword;

      if (studentResetScope === 'student') {
        const name = studentNameInput.trim();
        const className = studentClassInput.trim();
        if (!name) {
          setStudentResetError('请先填写学生姓名。');
          return;
        }
        if (!className) {
          setStudentResetError('请先填写学生班级。');
          return;
        }
        const identifyRes = await fetch(`${apiBase}/auth/student/identify`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, class_name: className }),
        });
        if (!identifyRes.ok) {
          const text = await identifyRes.text();
          throw new Error(text || `状态码 ${identifyRes.status}`);
        }
        const identifyData = (await identifyRes.json()) as StudentIdentifyResponse;
        if (!identifyData.ok || !identifyData.candidate_id) {
          const errorCode = toText(identifyData.error);
          if (errorCode === 'multiple') {
            setStudentResetError('同名学生，请补充准确班级后重试。');
          } else {
            setStudentResetError(identifyData.message || '未找到该学生。');
          }
          return;
        }
        payload.student_id = identifyData.candidate_id;
      } else if (studentResetScope === 'class') {
        const className = targetClassNameInput.trim();
        if (!className) {
          setStudentResetError('请先填写班级名称。');
          return;
        }
        payload.class_name = className;
      } else if (studentResetScope === 'all') {
        if (!isAdmin) {
          setStudentResetError('仅管理员可以重置全部学生密码。');
          return;
        }
        if (!confirmResetAll) {
          setStudentResetError('请勾选“确认重置全部学生密码”。');
          return;
        }
      }

      const resetRes = await fetch(`${apiBase}/auth/teacher/student/reset-passwords`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify(payload),
      });
      let resetData: TeacherStudentPasswordResetResponse | null = null;
      try {
        resetData = (await resetRes.json()) as TeacherStudentPasswordResetResponse;
      } catch {
        resetData = null;
      }
      if (!resetRes.ok) {
        const detail =
          toText((resetData as Record<string, unknown> | null)?.error) ||
          toText((resetData as Record<string, unknown> | null)?.message);
        const raw =
          detail ||
          toText((resetData as Record<string, unknown> | null)?.detail) ||
          `状态码 ${resetRes.status}`;
        throw new Error(mapStudentResetError(raw, raw));
      }
      if (!resetData?.ok) {
        const code = toText(resetData?.error);
        const message = mapStudentResetError(code, resetData?.message || '重置学生密码失败。');
        setStudentResetError(message);
        return;
      }

      const items = Array.isArray(resetData.items) ? resetData.items : [];
      const count = Number(resetData.count || items.length || 0);
      if (!items.length) {
        setStudentResetError('未返回可分发密码，请重试。');
        return;
      }
      setStudentResetItems(items);
      setStudentResetInfo(`已重置 ${count} 个学生密码。请立即保存下方新密码。`);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error || '重置学生密码失败');
      setStudentResetError(message);
    } finally {
      setStudentResetSubmitting(false);
    }
  };

  const handleCopyStudentPasswords = async () => {
    if (!studentResetItems.length) {
      setStudentResetError('当前没有可复制的密码结果。');
      return;
    }
    try {
      const rows = buildStudentPasswordRows(studentResetItems);
      await navigator.clipboard.writeText(rows);
      setStudentResetInfo('密码结果已复制。');
    } catch {
      setStudentResetError('复制失败，请手动复制列表内容。');
    }
  };

  // Keep state mounted while closed so form fields survive panel dismiss, matching the previous Topbar-owned state.
  if (!open) return null;

  return (
    <TeacherAdminPanel
      panelRef={panelRef}
      authed={authed}
      authSubjectLabel={authSubjectLabel}
      onOpenModelSettingsPanel={onOpenModelSettingsPanel}
      onClose={onClose}
    >
      {!authed ? (
        <section className="grid gap-2.5">
          <div className="grid gap-1">
            <div className="text-sm font-semibold">管理员登录</div>
            <div className="text-xs text-muted">学校教务使用管理员账号，不走教师 identify。</div>
          </div>
          <form className="grid gap-2" onSubmit={handleAdminLogin}>
            <div className="grid gap-1">
              <label className="text-xs text-muted" htmlFor={adminUsernameInputId}>
                管理员用户名
              </label>
              <input
                id={adminUsernameInputId}
                value={adminUsernameInput}
                onChange={(event) => setAdminUsernameInput(event.target.value)}
                autoComplete="username"
              />
            </div>
            <div className="grid gap-1">
              <label className="text-xs text-muted" htmlFor={adminPasswordInputId}>
                管理员密码
              </label>
              <input
                id={adminPasswordInputId}
                type="password"
                value={adminPasswordInput}
                onChange={(event) => setAdminPasswordInput(event.target.value)}
                autoComplete="current-password"
              />
            </div>
            <button
              type="submit"
              className="border-none rounded-[10px] px-3 py-[9px] bg-accent text-white cursor-pointer"
              disabled={adminSubmitting}
            >
              {adminSubmitting ? '登录中…' : '管理员登录'}
            </button>
          </form>
        </section>
      ) : null}
      <section className="grid gap-2.5">
        <div className="grid gap-1">
          <div className="text-sm font-semibold">身份验证</div>
          <div className="text-xs text-muted">用姓名和凭证确认教师身份。</div>
        </div>
        <form className="grid gap-2" onSubmit={handleAuthSubmit}>
          <div className="grid gap-1">
            <label className="text-xs text-muted" htmlFor={nameInputId}>
              姓名
            </label>
            <input
              id={nameInputId}
              value={nameInput}
              onChange={(event) => setNameInput(event.target.value)}
              placeholder="例如：张老师"
              autoComplete="name"
            />
          </div>
          <div className="grid gap-1">
            <label className="text-xs text-muted" htmlFor={emailInputId}>
              邮箱（同名时必填）
            </label>
            <input
              id={emailInputId}
              value={emailInput}
              onChange={(event) => setEmailInput(event.target.value)}
              placeholder="name@example.com"
              autoComplete="email"
            />
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className={`ghost ${credentialType === 'token' ? 'font-semibold' : ''}`}
              onClick={() => setCredentialType('token')}
            >
              token
            </button>
            <button
              type="button"
              className={`ghost ${credentialType === 'password' ? 'font-semibold' : ''}`}
              onClick={() => setCredentialType('password')}
            >
              密码
            </button>
          </div>
          <div className="grid gap-1">
            <label className="text-xs text-muted" htmlFor={credentialInputId}>
              {credentialType === 'token' ? 'token' : '密码'}
            </label>
            <input
              id={credentialInputId}
              type={credentialType === 'token' ? 'text' : 'password'}
              value={credentialInput}
              onChange={(event) => setCredentialInput(event.target.value)}
              placeholder={credentialType === 'token' ? '输入分发 token' : '输入已设置密码'}
              autoComplete={credentialType === 'token' ? 'off' : 'current-password'}
            />
          </div>
          <button
            type="submit"
            className="border-none rounded-[10px] px-3 py-[9px] bg-accent text-white cursor-pointer"
            disabled={submitting}
          >
            {submitting ? '认证中…' : '确认认证'}
          </button>
        </form>
      </section>
      <section className="grid gap-2.5 border-t border-[color:color-mix(in_oklab,var(--color-border)_72%,var(--color-surface))] pt-3">
        <div className="grid gap-1">
          <div className="text-sm font-semibold">密码设置</div>
          <div className="text-xs text-muted">设置或更新当前账号密码。</div>
        </div>
        <form className="grid gap-2" onSubmit={handleSetPassword}>
          <div className="text-xs text-muted">使用当前凭证验证后设置新密码。</div>
          <div className="grid gap-1">
            <label className="text-xs text-muted" htmlFor={newPasswordInputId}>
              新密码
            </label>
            <input
              id={newPasswordInputId}
              type="password"
              value={newPasswordInput}
              onChange={(event) => setNewPasswordInput(event.target.value)}
              placeholder="至少 8 位，含字母和数字"
              autoComplete="new-password"
            />
          </div>
          <button
            type="submit"
            className="border-none rounded-[10px] px-3 py-[9px] bg-accent text-white cursor-pointer"
            disabled={settingPassword}
          >
            {settingPassword ? '设置中…' : '设置密码'}
          </button>
        </form>
      </section>

      {authed ? (
        <section className="grid gap-2.5 border-t border-[color:color-mix(in_oklab,var(--color-border)_72%,var(--color-surface))] pt-3">
          <div className="grid gap-1">
            <div className="text-sm font-semibold">学生密码管理</div>
            <div className="text-xs text-muted">
              {isAdmin ? '按学生、班级或全部学生重置密码。' : '按学生或班级重置密码。'}
            </div>
          </div>
          <form className="grid gap-2" onSubmit={handleStudentPasswordReset}>
            <div className="flex items-center gap-2 flex-wrap">
              <button
                type="button"
                className={`ghost ${studentResetScope === 'student' ? 'font-semibold' : ''}`}
                onClick={() => setStudentResetScope('student')}
              >
                单个学生
              </button>
              <button
                type="button"
                className={`ghost ${studentResetScope === 'class' ? 'font-semibold' : ''}`}
                onClick={() => setStudentResetScope('class')}
              >
                按班级
              </button>
              {isAdmin ? (
                <button
                  type="button"
                  className={`ghost ${studentResetScope === 'all' ? 'font-semibold' : ''}`}
                  onClick={() => setStudentResetScope('all')}
                >
                  全部学生
                </button>
              ) : null}
            </div>
            {studentResetScope === 'student' ? (
              <>
                <div className="grid gap-1">
                  <label className="text-xs text-muted" htmlFor={studentNameInputId}>
                    学生姓名
                  </label>
                  <input
                    id={studentNameInputId}
                    value={studentNameInput}
                    onChange={(event) => setStudentNameInput(event.target.value)}
                    placeholder="例如：刘昊然"
                    autoComplete="off"
                  />
                </div>
                <div className="grid gap-1">
                  <label className="text-xs text-muted" htmlFor={studentClassInputId}>
                    学生班级
                  </label>
                  <input
                    id={studentClassInputId}
                    value={studentClassInput}
                    onChange={(event) => setStudentClassInput(event.target.value)}
                    placeholder="例如：高二2403班"
                    autoComplete="off"
                  />
                </div>
              </>
            ) : null}
            {studentResetScope === 'class' ? (
              <div className="grid gap-1">
                <label className="text-xs text-muted" htmlFor={targetClassInputId}>
                  目标班级
                </label>
                <input
                  id={targetClassInputId}
                  value={targetClassNameInput}
                  onChange={(event) => setTargetClassNameInput(event.target.value)}
                  placeholder="例如：高二2403班"
                  autoComplete="off"
                />
              </div>
            ) : null}
            {isAdmin && studentResetScope === 'all' ? (
              <label
                className="text-xs text-muted flex items-center gap-2"
                htmlFor={confirmResetAllId}
              >
                <input
                  id={confirmResetAllId}
                  type="checkbox"
                  checked={confirmResetAll}
                  onChange={(event) => setConfirmResetAll(event.target.checked)}
                />
                我确认重置全部学生密码
              </label>
            ) : null}
            <div className="grid gap-1">
              <label className="text-xs text-muted" htmlFor={studentResetPasswordInputId}>
                指定密码（可选）
              </label>
              <input
                id={studentResetPasswordInputId}
                type="password"
                value={studentResetPasswordInput}
                onChange={(event) => setStudentResetPasswordInput(event.target.value)}
                placeholder="留空则系统生成默认密码"
                autoComplete="new-password"
              />
            </div>
            <button
              type="submit"
              className="border-none rounded-[10px] px-3 py-[9px] bg-accent text-white cursor-pointer"
              disabled={studentResetSubmitting}
            >
              {studentResetSubmitting ? '重置中…' : '重置学生密码'}
            </button>
            {studentResetItems.length ? (
              <div className="grid gap-1.5">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-xs text-muted">结果列表（{studentResetItems.length}）</div>
                  <button
                    type="button"
                    className="ghost"
                    onClick={() => void handleCopyStudentPasswords()}
                  >
                    复制结果
                  </button>
                </div>
                <div className="max-h-[180px] overflow-auto rounded-lg border border-border bg-white p-2 text-[12px] leading-5">
                  {studentResetItems.slice(0, 80).map((item, index) => (
                    <div
                      key={`${toText(item.student_id)}-${index}`}
                      className="font-mono break-all"
                    >
                      {toText(item.student_id)},{toText(item.student_name)},
                      {toText(item.class_name)},{toText(item.temp_password)}
                    </div>
                  ))}
                </div>
                {studentResetItems.length > 80 ? (
                  <div className="text-xs text-muted">仅展示前 80 条，复制可获取完整结果。</div>
                ) : null}
              </div>
            ) : null}
          </form>
        </section>
      ) : null}

      {needEmail ? (
        <div className="text-xs text-muted">检测到同名教师，请补充邮箱后重试。</div>
      ) : null}
      {authError ? <div className="status err">{authError}</div> : null}
      {authInfo ? <div className="status ok">{authInfo}</div> : null}
      {studentResetError ? <div className="status err">{studentResetError}</div> : null}
      {studentResetInfo ? <div className="status ok">{studentResetInfo}</div> : null}
      {authed ? (
        <button
          type="button"
          className="ghost justify-start"
          onClick={() => {
            clearTeacherAuthSession();
            setAuthInfo('');
            setAuthError('');
            setStudentResetError('');
            setStudentResetInfo('');
            setStudentResetItems([]);
          }}
        >
          退出认证
        </button>
      ) : null}
    </TeacherAdminPanel>
  );
}
