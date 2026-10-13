import { useEffect, useId, useState, type FormEvent } from 'react';

import { resolveRuntimeApiBase } from '../../../../shared/apiBase';
import { safeLocalStorageGetItem } from '../../utils/storage';
import { readTeacherAccessToken, TEACHER_AUTH_EVENT, writeTeacherAuthSession } from './teacherAuth';

type TeacherAuthPanelProps = {
  authed: boolean;
  onClose: () => void;
};

type TeacherIdentifyResponse = {
  ok: boolean;
  error?: string;
  message?: string;
  candidate_id?: string;
  need_email_disambiguation?: boolean;
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
  access_token?: string;
  subject_id?: string;
  role?: string;
  teacher?: {
    teacher_id?: string;
    teacher_name?: string;
    email?: string;
  };
};

const toText = (value: unknown): string => String(value ?? '').trim();

export function useTeacherAuthPanel(onClose: () => void) {
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

  useEffect(() => {
    const clearStatusIfLoggedOut = () => {
      if (readTeacherAccessToken()) return;
      setAuthError('');
      setAuthInfo('');
    };
    window.addEventListener(TEACHER_AUTH_EVENT, clearStatusIfLoggedOut);
    return () => window.removeEventListener(TEACHER_AUTH_EVENT, clearStatusIfLoggedOut);
  }, []);

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

      const teacher = setPasswordData.teacher || {};
      const teacherId = toText(
        setPasswordData.subject_id || teacher.teacher_id || identifyData.candidate_id,
      );
      const teacherName = toText(teacher.teacher_name || name || teacherId);
      const teacherEmail = toText(teacher.email || email);
      const accessToken = toText(setPasswordData.access_token);
      // tv increments on set-password; persist only the rotated token (never claim the old Bearer).
      if (accessToken) {
        writeTeacherAuthSession({
          accessToken,
          teacherId,
          teacherName,
          role: toText(setPasswordData.role) || 'teacher',
          ...(teacherEmail ? { email: teacherEmail } : {}),
        });
      }

      setCredentialType('password');
      setNewPasswordInput('');
      setAuthInfo('密码设置成功，后续可使用密码登录。');
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error || '设置密码失败');
      setAuthError(message);
    } finally {
      setSettingPassword(false);
    }
  };

  return {
    nameInput,
    setNameInput,
    emailInput,
    setEmailInput,
    credentialInput,
    setCredentialInput,
    credentialType,
    setCredentialType,
    newPasswordInput,
    setNewPasswordInput,
    needEmail,
    submitting,
    settingPassword,
    authError,
    authInfo,
    adminUsernameInput,
    setAdminUsernameInput,
    adminPasswordInput,
    setAdminPasswordInput,
    adminSubmitting,
    adminUsernameInputId,
    adminPasswordInputId,
    nameInputId,
    emailInputId,
    credentialInputId,
    newPasswordInputId,
    handleAdminLogin,
    handleAuthSubmit,
    handleSetPassword,
  };
}

export function TeacherAuthPanelView({
  authed,
  model,
}: {
  authed: boolean;
  model: ReturnType<typeof useTeacherAuthPanel>;
}) {
  const {
    nameInput,
    setNameInput,
    emailInput,
    setEmailInput,
    credentialInput,
    setCredentialInput,
    credentialType,
    setCredentialType,
    newPasswordInput,
    setNewPasswordInput,
    needEmail,
    submitting,
    settingPassword,
    authError,
    authInfo,
    adminUsernameInput,
    setAdminUsernameInput,
    adminPasswordInput,
    setAdminPasswordInput,
    adminSubmitting,
    adminUsernameInputId,
    adminPasswordInputId,
    nameInputId,
    emailInputId,
    credentialInputId,
    newPasswordInputId,
    handleAdminLogin,
    handleAuthSubmit,
    handleSetPassword,
  } = model;

  return (
    <>
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
              className="border-none rounded-[10px] px-3 py-[9px] bg-accent text-on-accent cursor-pointer"
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
            className="border-none rounded-[10px] px-3 py-[9px] bg-accent text-on-accent cursor-pointer"
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
            className="border-none rounded-[10px] px-3 py-[9px] bg-accent text-on-accent cursor-pointer"
            disabled={settingPassword}
          >
            {settingPassword ? '设置中…' : '设置密码'}
          </button>
        </form>
      </section>
      {needEmail ? (
        <div className="text-xs text-muted">检测到同名教师，请补充邮箱后重试。</div>
      ) : null}
      {authError ? <div className="status err">{authError}</div> : null}
      {authInfo ? <div className="status ok">{authInfo}</div> : null}
    </>
  );
}

export default function TeacherAuthPanel({ authed, onClose }: TeacherAuthPanelProps) {
  const model = useTeacherAuthPanel(onClose);
  return <TeacherAuthPanelView authed={authed} model={model} />;
}
