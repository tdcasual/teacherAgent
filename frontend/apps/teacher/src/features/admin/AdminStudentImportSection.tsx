import { useId, useState, type FormEvent } from 'react';

import AdminTempPasswordOnce from './AdminTempPasswordOnce';
import { adminTokenHeaders, errorDetail, toText } from './adminSchoolApi';

type ImportItem = {
  student_id?: string;
  student_name?: string;
  class_name?: string;
  temp_password?: string;
  created?: boolean;
};

const IMPORT_ERRORS: Record<string, string> = {
  unknown_column: 'CSV 只能包含 student_name、class_name，可选 student_id。',
  missing_column: 'CSV 必须包含 student_name 和 class_name 列。',
  missing_student_name: '有行缺少学生姓名。',
  missing_class_name: '有行缺少班级。',
  invalid_student_id: 'student_id 非法。',
  too_many_rows: '最多 2000 行。',
  file_too_large: 'CSV 不能超过 256KB。',
  empty_csv: 'CSV 没有学生行。',
  invalid_encoding: '请使用 UTF-8 CSV。',
};

export default function AdminStudentImportSection({ apiBase }: { apiBase: string }) {
  const formId = useId();
  const fileId = `${formId}-file`;
  const resetId = `${formId}-reset`;
  const [file, setFile] = useState<File | null>(null);
  const [resetPasswords, setResetPasswords] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  const [items, setItems] = useState<ImportItem[]>([]);

  const handleImport = async (event: FormEvent) => {
    event.preventDefault();
    if (!file) {
      setError('请选择 CSV 文件。');
      return;
    }
    setError('');
    setInfo('');
    setItems([]);
    setSubmitting(true);
    try {
      const body = new FormData();
      body.append('file', file);
      body.append('reset_passwords', resetPasswords ? 'true' : 'false');
      const res = await fetch(`${apiBase}/auth/admin/students/import`, {
        method: 'POST',
        headers: adminTokenHeaders(),
        body,
      });
      const data = (await res.json()) as {
        ok?: boolean;
        detail?: string;
        error?: string;
        message?: string;
        created?: number;
        updated?: number;
        items?: ImportItem[];
      };
      if (!res.ok || !data.ok) {
        const code = toText(data.detail || data.error);
        setError(IMPORT_ERRORS[code] || errorDetail(data, '导入失败。'));
        return;
      }
      setItems(Array.isArray(data.items) ? data.items : []);
      setInfo(
        `已写入 student_auth：新建 ${data.created ?? 0}，更新 ${data.updated ?? 0}。导入不会自动编班，请在下方加任教后整班入学。`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : '导入失败');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form className="grid gap-3 rounded-2xl border border-border p-4" onSubmit={handleImport}>
      <div className="text-sm font-semibold">导入学生名册</div>
      <div className="text-xs text-muted">
        只创建/更新登录账号，不自动 enroll。表头：student_name,class_name，可选 student_id。
      </div>
      <div className="grid gap-1">
        <label className="text-xs text-muted" htmlFor={fileId}>
          名册 CSV
        </label>
        <input
          id={fileId}
          type="file"
          accept=".csv,text/csv"
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        />
      </div>
      <label className="flex items-center gap-2 text-sm" htmlFor={resetId}>
        <input
          id={resetId}
          type="checkbox"
          checked={resetPasswords}
          onChange={(event) => setResetPasswords(event.target.checked)}
        />
        重导时重置密码
      </label>
      <button
        type="submit"
        className="border-none rounded-[10px] px-3 py-[9px] bg-accent text-white cursor-pointer w-fit"
        disabled={submitting}
      >
        {submitting ? '导入中…' : '导入名册'}
      </button>
      {error ? <div className="status err">{error}</div> : null}
      {info ? <div className="status ok">{info}</div> : null}
      {items.length ? (
        <div className="grid gap-2">
          {items.map((item) => {
            const studentId = toText(item.student_id);
            const password = toText(item.temp_password);
            return (
              <div key={studentId} className="grid gap-1 rounded-lg border border-border px-3 py-2">
                <div className="text-sm">
                  {toText(item.student_name)} · {toText(item.class_name)}
                </div>
                <div className="text-xs text-muted font-mono break-all">{studentId}</div>
                {password ? <AdminTempPasswordOnce password={password} /> : null}
              </div>
            );
          })}
        </div>
      ) : null}
    </form>
  );
}
