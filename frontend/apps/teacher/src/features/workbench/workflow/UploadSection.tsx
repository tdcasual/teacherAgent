import { useEffect, useMemo, useState } from 'react'

import { resolveRuntimeApiBase } from '../../../../../shared/apiBase'
import { readTeacherAccessToken } from '../../auth/teacherAuth'
import { safeLocalStorageGetItem } from '../../../utils/storage'
import type { UploadScope, UploadSectionProps } from '../../../types/workflow'
import LabeledField from './LabeledField'

const ASSIGNMENT_SUBJECT_OPTIONS = [
  { id: 'physics', label: '物理' },
  { id: 'math', label: '数学' },
  { id: 'generic', label: '通用' },
] as const

type RosterItem = {
  teacher_id?: string
  subject_id?: string
  class_name?: string
}

type Props = UploadSectionProps & {
  uploading: boolean
  examUploading: boolean
}

export default function UploadSection(props: Props) {
  const [rosterItems, setRosterItems] = useState<RosterItem[]>([])
  useEffect(() => {
    const token = readTeacherAccessToken()
    if (!token) {
      setRosterItems([])
      return
    }
    const apiBase = resolveRuntimeApiBase(safeLocalStorageGetItem('apiBaseTeacher'))
    let cancelled = false
    void fetch(`${apiBase}/teacher/roster`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (res) => (res.ok ? ((await res.json()) as { items?: RosterItem[] }) : { items: [] }))
      .then((payload) => {
        if (!cancelled) setRosterItems(Array.isArray(payload.items) ? payload.items : [])
      })
      .catch(() => {
        if (!cancelled) setRosterItems([])
      })
    return () => {
      cancelled = true
    }
  }, [])

  const {
    uploadMode, setUploadMode, uploadCardCollapsed, setUploadCardCollapsed,
    formatUploadJobSummary, formatExamJobSummary, uploadJobInfo, uploadAssignmentId,
    examJobInfo, examId, handleUploadAssignment, handleUploadExam,
    setUploadAssignmentId, uploadDate, setUploadDate, uploadDueAt, setUploadDueAt,
    uploadSubjectId, setUploadSubjectId, uploadScope, setUploadScope,
    uploadClassName, setUploadClassName, uploadStudentIds, setUploadStudentIds,
    setUploadFiles, setUploadAnswerFiles, uploading, uploadError, uploadStatus,
    setExamId, examDate, setExamDate, examClassName, setExamClassName,
    setExamPaperFiles, setExamAnswerFiles, setExamScoreFiles,
    examUploading, examUploadError, examUploadStatus,
  } = props

  const staticLabel = (id: string) =>
    ASSIGNMENT_SUBJECT_OPTIONS.find((option) => option.id === id)?.label || id

  const subjectOptions = useMemo(() => {
    const rosterSubjects = Array.from(
      new Set(rosterItems.map((item) => String(item.subject_id || '').trim()).filter(Boolean)),
    )
    const ids = rosterSubjects.length ? rosterSubjects : ASSIGNMENT_SUBJECT_OPTIONS.map((option) => option.id)
    const merged = ids.includes(uploadSubjectId) ? ids : [uploadSubjectId, ...ids]
    return merged.map((id) => ({ id, label: staticLabel(id) }))
  }, [rosterItems, uploadSubjectId])

  const classOptions = useMemo(
    () =>
      Array.from(
        new Set(
          rosterItems
            .filter((item) => String(item.subject_id || '').trim() === uploadSubjectId)
            .map((item) => String(item.class_name || '').trim())
            .filter(Boolean),
        ),
      ),
    [rosterItems, uploadSubjectId],
  )

  return (
              <section id="workflow-upload-section" className={`bg-surface border border-border rounded-[14px] shadow-sm ${uploadCardCollapsed ? 'py-[10px] px-3' : 'p-[10px]'}`}>
    	            <div className={`panel-header flex items-start gap-2 flex-wrap ${uploadCardCollapsed ? 'mb-0' : 'mb-2'}`}>
    	              <div className="flex items-center gap-3 min-w-0 flex-1">
    	                <h3 className="m-0 whitespace-nowrap shrink-0">{uploadMode === 'assignment' ? '上传作业文件（文档 / 图片）' : '上传考试文件（试卷 + 成绩表）'}</h3>
    	                <div className="inline-flex border border-border rounded-lg overflow-hidden bg-white shrink-0">
    	                  <button
    	                    type="button"
    	                    className={`border-0 bg-transparent py-1.5 px-3 cursor-pointer text-[12px] text-muted ${uploadMode === 'assignment' ? 'active bg-accent-soft text-accent font-semibold' : ''}`}
    	                    onClick={() => setUploadMode('assignment')}
    	                  >
    	                    作业
    	                  </button>
    	                  <button type="button" className={`border-0 bg-transparent py-1.5 px-3 cursor-pointer text-[12px] text-muted border-l border-border ${uploadMode === 'exam' ? 'active bg-accent-soft text-accent font-semibold' : ''}`} onClick={() => setUploadMode('exam')}>
    	                    考试
    	                  </button>
    	                </div>
    	              </div>
    	              {uploadCardCollapsed ? (
    	                  <div
    	                    className="panel-summary flex-1 min-w-0 text-muted text-[12px] whitespace-nowrap overflow-hidden text-ellipsis"
    	                    title={
    	                      uploadMode === 'assignment'
    	                      ? formatUploadJobSummary(uploadJobInfo, uploadAssignmentId.trim())
    	                      : formatExamJobSummary(examJobInfo, examId.trim())
    	                  }
    	                >
    	                  {uploadMode === 'assignment'
    	                    ? formatUploadJobSummary(uploadJobInfo, uploadAssignmentId.trim())
    	                    : formatExamJobSummary(examJobInfo, examId.trim())}
    	                </div>
    	              ) : null}
	    	              <button type="button" className="ghost" onClick={() => setUploadCardCollapsed((v) => !v)}>
    	                {uploadCardCollapsed ? '展开' : '收起'}
    	              </button>
    	            </div>
    	            {uploadCardCollapsed ? null : (
    	              <>
    	                {uploadMode === 'assignment' ? (
    	                  <>
    	                    <p className="m-0 mb-3 text-muted">上传后将在后台解析题目与答案，并生成作业 8 点描述。解析完成后需确认创建作业。</p>
    	                    <form className="upload-form grid gap-[10px]" onSubmit={handleUploadAssignment}>
    	                      <div className="grid gap-[10px] grid-cols-1">
    	                        <LabeledField label="作业编号">
    	                          <input
    	                            value={uploadAssignmentId}
    	                            onChange={(e) => setUploadAssignmentId(e.target.value)}
    	                            placeholder="例如：HW-2026-02-05"
    	                          />
    	                        </LabeledField>
    	                        <LabeledField label="日期（可选）">
    	                          <input value={uploadDate} onChange={(e) => setUploadDate(e.target.value)} placeholder="YYYY-MM-DD" />
    	                        </LabeledField>
    	                        <LabeledField label="截止日期（可选）">
    	                          <input value={uploadDueAt} onChange={(e) => setUploadDueAt(e.target.value)} placeholder="YYYY-MM-DD 或 ISO 时间" />
    	                        </LabeledField>
    	                        <LabeledField label="学科">
    	                          <select value={uploadSubjectId} onChange={(e) => setUploadSubjectId(e.target.value)}>
    	                            {subjectOptions.map((option) => (
    	                              <option key={option.id} value={option.id}>{option.label}</option>
    	                            ))}
    	                          </select>
    	                        </LabeledField>
    	                        <LabeledField label="范围">
    	                          <select value={uploadScope} onChange={(e) => setUploadScope(e.target.value as UploadScope)}>
    	                            <option value="public">公共作业</option>
    	                            <option value="class">班级作业</option>
    	                            <option value="student">私人作业</option>
    	                          </select>
    	                        </LabeledField>
    	                        <LabeledField label="班级（班级作业必填）">
    	                          {classOptions.length ? (
    	                            <select value={uploadClassName} onChange={(e) => setUploadClassName(e.target.value)}>
    	                              <option value="">选择班级</option>
    	                              {classOptions.map((className) => (
    	                                <option key={className} value={className}>{className}</option>
    	                              ))}
    	                            </select>
    	                          ) : (
    	                            <input
    	                              value={uploadClassName}
    	                              onChange={(e) => setUploadClassName(e.target.value)}
    	                              placeholder="例如：高二2403班"
    	                            />
    	                          )}
    	                        </LabeledField>
    	                        <LabeledField label="学生编号（私人作业必填）">
    	                          <input
    	                            value={uploadStudentIds}
    	                            onChange={(e) => setUploadStudentIds(e.target.value)}
    	                            placeholder="例如：高二2403班_刘昊然"
    	                          />
    	                        </LabeledField>
    	                        <LabeledField label="作业文件（文档/图片）">
    	                          <input
    	                            type="file"
    	                            multiple
    	                            accept="application/pdf,image/*,.md,.markdown,.tex"
    	                            onChange={(e) => setUploadFiles(Array.from(e.target.files || []))}
    	                          />
    	                        </LabeledField>
    	                        <LabeledField label="答案文件（可选）">
    	                          <input
    	                            type="file"
    	                            multiple
    	                            accept="application/pdf,image/*,.md,.markdown,.tex"
    	                            onChange={(e) => setUploadAnswerFiles(Array.from(e.target.files || []))}
    	                          />
    	                        </LabeledField>
    	                      </div>
    	                      <button type="submit" className="border-none rounded-xl py-[10px] px-[14px] bg-accent text-white cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed min-h-11" disabled={uploading}>
    	                        {uploading ? '上传中…' : '上传并开始解析'}
    	                      </button>
    	                    </form>
    	                    {uploadError && <div className="mt-[10px] p-[10px_12px] rounded-xl text-[12px] whitespace-pre-wrap overflow-x-auto bg-danger-soft text-danger">{uploadError}</div>}
    	                    {uploadStatus && <pre className="mt-[10px] p-[10px_12px] rounded-xl text-[12px] whitespace-pre-wrap overflow-x-auto bg-success-soft text-success">{uploadStatus}</pre>}
    	                  </>
    	                ) : (
    	                  <>
    	                    <p className="m-0 mb-3 text-muted">上传考试试卷、标准答案（可选）与成绩表后，系统将生成考试数据与分析草稿。成绩表推荐电子表格（最稳）。</p>
    	                    <form className="upload-form grid gap-[10px]" onSubmit={handleUploadExam}>
    	                      <div className="grid gap-[10px] grid-cols-1">
    	                        <LabeledField label="考试编号（可选）">
    	                          <input value={examId} onChange={(e) => setExamId(e.target.value)} placeholder="例如：EX2403_PHY" />
    	                        </LabeledField>
    	                        <LabeledField label="日期（可选）">
    	                          <input value={examDate} onChange={(e) => setExamDate(e.target.value)} placeholder="YYYY-MM-DD" />
    	                        </LabeledField>
    	                        <LabeledField label="班级（可选）">
    	                          <input
    	                            value={examClassName}
    	                            onChange={(e) => setExamClassName(e.target.value)}
    	                            placeholder="例如：高二2403班"
    	                          />
    	                        </LabeledField>
    	                        <LabeledField label="试卷文件（必填）">
    	                          <input
    	                            type="file"
    	                            multiple
    	                            accept="application/pdf,image/*,.md,.markdown,.tex"
    	                            onChange={(e) => setExamPaperFiles(Array.from(e.target.files || []))}
    	                          />
    	                        </LabeledField>
    	                        <LabeledField label="答案文件（可选）">
    	                          <input
    	                            type="file"
    	                            multiple
    	                            accept="application/pdf,image/*,.md,.markdown,.tex"
    	                            onChange={(e) => setExamAnswerFiles(Array.from(e.target.files || []))}
    	                          />
    	                        </LabeledField>
    	                        <LabeledField label="成绩文件（必填）">
    	                          <input
    	                            type="file"
    	                            multiple
    	                            accept="application/pdf,image/*,.xls,.xlsx"
    	                            onChange={(e) => setExamScoreFiles(Array.from(e.target.files || []))}
    	                          />
    	                        </LabeledField>
    	                      </div>
    	                      <button type="submit" className="border-none rounded-xl py-[10px] px-[14px] bg-accent text-white cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed min-h-11" disabled={examUploading}>
    	                        {examUploading ? '上传中…' : '上传并开始解析'}
    	                      </button>
    	                    </form>
    	                    {examUploadError && <div className="mt-[10px] p-[10px_12px] rounded-xl text-[12px] whitespace-pre-wrap overflow-x-auto bg-danger-soft text-danger">{examUploadError}</div>}
    	                    {examUploadStatus && <pre className="mt-[10px] p-[10px_12px] rounded-xl text-[12px] whitespace-pre-wrap overflow-x-auto bg-success-soft text-success">{examUploadStatus}</pre>}
    	                  </>
    	                )}
    	              </>
    	            )}
    	          </section>
  )
}
