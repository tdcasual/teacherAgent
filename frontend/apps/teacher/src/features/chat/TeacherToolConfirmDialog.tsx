import { ConfirmDialog } from '../../../../shared/dialog';

export type TeacherToolConfirm = {
  confirm_id: string;
  tool: string;
  preview: string;
};

export async function postTeacherToolConfirm(
  apiBase: string,
  confirmId: string,
  confirmed: boolean,
): Promise<void> {
  const res = await fetch(`${apiBase}/teacher/tools/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ confirm_id: confirmId, confirmed }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `状态码 ${res.status}`);
  }
}

export function TeacherToolConfirmDialog({
  toolConfirm,
  onConfirm,
  onCancel,
}: {
  toolConfirm: TeacherToolConfirm | null;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <ConfirmDialog
      open={Boolean(toolConfirm)}
      title="确认执行写操作？"
      description={
        toolConfirm
          ? `${toolConfirm.tool}${toolConfirm.preview ? `\n${toolConfirm.preview}` : ''}`
          : undefined
      }
      confirmText="确认执行"
      confirmTone="danger"
      cancelText="取消"
      onCancel={onCancel}
      onConfirm={onConfirm}
    />
  );
}
