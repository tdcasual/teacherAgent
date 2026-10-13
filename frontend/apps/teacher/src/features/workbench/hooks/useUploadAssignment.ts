import { useCallback, type FormEvent } from 'react';
import { safeLocalStorageSetItem } from '../../../utils/storage';
import { toUserFacingErrorMessage } from '../../../../../shared/errorMessage';
import {
  ASSIGNMENT_UPLOAD_ALLOWED_SUFFIXES,
  ASSIGNMENT_UPLOAD_MAX_FILE_BYTES,
  ASSIGNMENT_UPLOAD_MAX_FILES_PER_FIELD,
  ASSIGNMENT_UPLOAD_MAX_TOTAL_BYTES,
  validateFilesBeforeUpload,
} from '../../../../../shared/uploadValidation';
import type { UseAssignmentWorkflowParams } from '../../../types/workflow';

const toErrorMessage = (error: unknown, fallback = '请求失败') => {
  return toUserFacingErrorMessage(error, fallback);
};

export function useUploadAssignment(params: UseAssignmentWorkflowParams) {
  const {
    apiBase,
    assignmentKind,
    uploadAssignmentId,
    uploadDate,
    uploadDueAt,
    uploadSubjectId,
    uploadScope,
    uploadClassName,
    uploadStudentIds,
    uploadFiles,
    uploadAnswerFiles,
    setUploadError,
    setUploadStatus,
    setUploadJobId,
    setUploadJobInfo,
    setUploadDraft,
    setUploadFiles,
    setUploadAnswerFiles,
    setUploading,
    setUploadCardCollapsed,
    setDraftPanelCollapsed,
    setDraftError,
    setDraftActionStatus,
    setDraftActionError,
  } = params;

  const handleUploadAssignment = useCallback(
    async (event: FormEvent) => {
      event.preventDefault();
      setUploadError('');
      setUploadStatus('');
      setUploadJobId('');
      setUploadJobInfo(null);
      setUploadDraft(null);
      setDraftPanelCollapsed(false);
      setDraftError('');
      setDraftActionStatus('');
      setDraftActionError('');
      setUploadCardCollapsed(false);
      if (!uploadAssignmentId.trim()) {
        setUploadError('请填写作业编号');
        return;
      }
      if (!uploadFiles.length) {
        setUploadError('请至少上传一份作业文件（文档或图片）');
        return;
      }
      const sourceFileCheck = validateFilesBeforeUpload(uploadFiles, {
        label: '作业文件',
        maxCount: ASSIGNMENT_UPLOAD_MAX_FILES_PER_FIELD,
        maxFileBytes: ASSIGNMENT_UPLOAD_MAX_FILE_BYTES,
        allowedSuffixes: ASSIGNMENT_UPLOAD_ALLOWED_SUFFIXES,
      });
      if (sourceFileCheck) {
        setUploadError(sourceFileCheck);
        return;
      }
      const answerFileCheck = validateFilesBeforeUpload(uploadAnswerFiles, {
        label: '答案文件',
        maxCount: ASSIGNMENT_UPLOAD_MAX_FILES_PER_FIELD,
        maxFileBytes: ASSIGNMENT_UPLOAD_MAX_FILE_BYTES,
        allowedSuffixes: ASSIGNMENT_UPLOAD_ALLOWED_SUFFIXES,
      });
      if (answerFileCheck) {
        setUploadError(answerFileCheck);
        return;
      }
      const totalUploadBytes = [...uploadFiles, ...uploadAnswerFiles].reduce(
        (sum, file) => sum + Math.max(0, Number(file.size || 0)),
        0,
      );
      if (totalUploadBytes > ASSIGNMENT_UPLOAD_MAX_TOTAL_BYTES) {
        setUploadError(
          `作业上传总大小不能超过 ${ASSIGNMENT_UPLOAD_MAX_TOTAL_BYTES / (1024 * 1024)}MB`,
        );
        return;
      }
      if (uploadScope === 'student' && !uploadStudentIds.trim()) {
        setUploadError('私人作业请填写学生编号');
        return;
      }
      if (uploadScope === 'class' && !uploadClassName.trim()) {
        setUploadError('班级作业请填写班级');
        return;
      }
      if (!uploadSubjectId.trim()) {
        setUploadError('请选择学科');
        return;
      }
      setUploading(true);
      try {
        const fd = new FormData();
        fd.append('assignment_id', uploadAssignmentId.trim());
        if (uploadDate.trim()) fd.append('date', uploadDate.trim());
        if (uploadDueAt.trim()) fd.append('due_at', uploadDueAt.trim());
        fd.append('subject_id', uploadSubjectId.trim());
        fd.append('scope', uploadScope);
        if (uploadClassName.trim()) fd.append('class_name', uploadClassName.trim());
        if (uploadStudentIds.trim()) fd.append('student_ids', uploadStudentIds.trim());
        fd.append('assignment_kind', assignmentKind);
        uploadFiles.forEach((file) => fd.append('files', file));
        uploadAnswerFiles.forEach((file) => fd.append('answer_files', file));

        const res = await fetch(`${apiBase}/assignment/upload/start`, { method: 'POST', body: fd });
        if (!res.ok) {
          const text = await res.text();
          let message = text || `状态码 ${res.status}`;
          try {
            const parsed = JSON.parse(text);
            const detail = parsed?.detail || parsed;
            if (typeof detail === 'string') {
              message = detail;
            } else if (detail?.message) {
              const hints = Array.isArray(detail.hints) ? detail.hints.join('；') : '';
              message = `${detail.message}${hints ? `（${hints}）` : ''}`;
            }
          } catch (err) {
            // ignore JSON parse errors
          }
          throw new Error(message);
        }
        const data = await res.json();
        if (data && typeof data === 'object') {
          if (data.job_id) {
            const jid = String(data.job_id);
            setUploadJobId(jid);
            try {
              safeLocalStorageSetItem(
                'teacherActiveUpload',
                JSON.stringify({
                  type: 'assignment',
                  job_id: jid,
                  assignment_kind: assignmentKind,
                }),
              );
            } catch {
              // ignore
            }
          }
          const message = data.message || '解析任务已创建，后台处理中。';
          setUploadStatus(message);
        } else {
          setUploadStatus(typeof data === 'string' ? data : JSON.stringify(data, null, 2));
        }
        setUploadFiles([]);
        setUploadAnswerFiles([]);
      } catch (err: unknown) {
        setUploadError(toErrorMessage(err));
      } finally {
        setUploading(false);
      }
    },
    [
      apiBase,
      setDraftActionError,
      setDraftActionStatus,
      setDraftError,
      setDraftPanelCollapsed,
      setUploadAnswerFiles,
      setUploadCardCollapsed,
      setUploadDraft,
      setUploadError,
      setUploadFiles,
      setUploadJobId,
      setUploadJobInfo,
      setUploadStatus,
      setUploading,
      assignmentKind,
      uploadAnswerFiles,
      uploadAssignmentId,
      uploadClassName,
      uploadDate,
      uploadDueAt,
      uploadSubjectId,
      uploadFiles,
      uploadScope,
      uploadStudentIds,
    ],
  );

  return { handleUploadAssignment };
}
