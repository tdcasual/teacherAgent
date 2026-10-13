import { useId, useState, type FormEvent, type MutableRefObject } from 'react';

import { resolveRuntimeApiBase } from '../../../../shared/apiBase';
import { safeLocalStorageGetItem } from '../../utils/storage';
import { TeacherAuthPanelView, useTeacherAuthPanel } from '../auth/TeacherAuthPanel';
import {
  clearTeacherAuthSession,
  readTeacherAccessToken,
  readTeacherAuthRole,
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

type StudentIdentifyResponse = {
  ok: boolean;
  error?: string;
  message?: string;
  candidate_id?: string;
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
  const formId = useId();
  const studentNameInputId = `${formId}-student-name`;
  const studentClassInputId = `${formId}-student-class`;
  const targetClassInputId = `${formId}-target-class`;
  const studentResetPasswordInputId = `${formId}-student-reset-password`;
  const confirmResetAllId = `${formId}-confirm-reset-all`;
  const isAdmin = readTeacherAuthRole() === 'admin';
  const authModel = useTeacherAuthPanel(onClose);

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

  // Keep hook state mounted while closed so identity fields survive panel dismiss.
  if (!open) return null;

  return (
    <TeacherAdminPanel
      panelRef={panelRef}
      authed={authed}
      authSubjectLabel={authSubjectLabel}
      onOpenModelSettingsPanel={onOpenModelSettingsPanel}
      onClose={onClose}
    >
      <TeacherAuthPanelView authed={authed} model={authModel} />

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
              className="border-none rounded-[10px] px-3 py-[9px] bg-accent text-on-accent cursor-pointer"
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

      {studentResetError ? <div className="status err">{studentResetError}</div> : null}
      {studentResetInfo ? <div className="status ok">{studentResetInfo}</div> : null}
      {authed ? (
        <button
          type="button"
          className="ghost justify-start"
          onClick={() => {
            clearTeacherAuthSession();
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
