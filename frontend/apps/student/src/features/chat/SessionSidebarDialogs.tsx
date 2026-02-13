import { ConfirmDialog, PromptDialog } from '../../../../shared/dialog'
import type { SessionSidebarProps } from './sessionSidebarTypes'

type Props = Pick<
SessionSidebarProps,
| 'renameDialogSessionId'
| 'archiveDialogSessionId'
| 'getSessionTitle'
| 'archiveDialogActionLabel'
| 'archiveDialogIsArchived'
| 'cancelRenameDialog'
| 'confirmRenameDialog'
| 'cancelArchiveDialog'
| 'confirmArchiveDialog'
>

export default function SessionSidebarDialogs(props: Props) {
  const {
    renameDialogSessionId, archiveDialogSessionId, getSessionTitle, archiveDialogActionLabel,
    archiveDialogIsArchived, cancelRenameDialog, confirmRenameDialog, cancelArchiveDialog, confirmArchiveDialog,
  } = props

  return (
    <>
      <PromptDialog
        open={Boolean(renameDialogSessionId)}
        title="重命名会话"
        description="可留空以删除自定义名称。"
        label="会话名称"
        placeholder="输入会话名称"
        defaultValue={renameDialogSessionId ? getSessionTitle(renameDialogSessionId) : ''}
        confirmText="保存"
        onCancel={cancelRenameDialog}
        onConfirm={confirmRenameDialog}
      />
      <ConfirmDialog
        open={Boolean(archiveDialogSessionId)}
        title={`确认${archiveDialogActionLabel}会话？`}
        description={archiveDialogSessionId ? `会话：${getSessionTitle(archiveDialogSessionId)}` : undefined}
        confirmText={archiveDialogActionLabel}
        confirmTone={archiveDialogIsArchived ? 'primary' : 'danger'}
        cancelText="取消"
        onCancel={cancelArchiveDialog}
        onConfirm={confirmArchiveDialog}
      />
    </>
  )
}
