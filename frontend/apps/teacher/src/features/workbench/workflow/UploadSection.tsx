type UploadSectionProps = {
  uploadMode: string
  setUploadMode: any
  uploadCardCollapsed: boolean
  setUploadCardCollapsed: any
  formatUploadJobSummary: any
  formatExamJobSummary: any
  uploadJobInfo: any
  uploadAssignmentId: string
  examJobInfo: any
  examId: string
  handleUploadAssignment: any
  handleUploadExam: any
  setUploadAssignmentId: any
  uploadDate: string
  setUploadDate: any
  uploadScope: string
  setUploadScope: any
  uploadClassName: string
  setUploadClassName: any
  uploadStudentIds: string
  setUploadStudentIds: any
  setUploadFiles: any
  setUploadAnswerFiles: any
  uploading: boolean
  uploadError: any
  uploadStatus: any
  setExamId: any
  examDate: string
  setExamDate: any
  examClassName: string
  setExamClassName: any
  setExamPaperFiles: any
  setExamAnswerFiles: any
  setExamScoreFiles: any
  examUploading: boolean
  examUploadError: any
  examUploadStatus: any
}

export default function UploadSection(props: UploadSectionProps) {
  const {
    uploadMode, setUploadMode, uploadCardCollapsed, setUploadCardCollapsed,
    formatUploadJobSummary, formatExamJobSummary, uploadJobInfo, uploadAssignmentId,
    examJobInfo, examId, handleUploadAssignment, handleUploadExam,
    setUploadAssignmentId, uploadDate, setUploadDate, uploadScope, setUploadScope,
    uploadClassName, setUploadClassName, uploadStudentIds, setUploadStudentIds,
    setUploadFiles, setUploadAnswerFiles, uploading, uploadError, uploadStatus,
    setExamId, examDate, setExamDate, examClassName, setExamClassName,
    setExamPaperFiles, setExamAnswerFiles, setExamScoreFiles,
    examUploading, examUploadError, examUploadStatus,
  } = props

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
	    	              <button type="button" className="ghost" onClick={() => setUploadCardCollapsed((v: boolean) => !v)}>
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
    	                        <div className="grid gap-1.5">
    	                          <label>作业编号</label>
    	                          <input
    	                            value={uploadAssignmentId}
    	                            onChange={(e) => setUploadAssignmentId(e.target.value)}
    	                            placeholder="例如：HW-2026-02-05"
    	                          />
    	                        </div>
    	                        <div className="grid gap-1.5">
    	                          <label>日期（可选）</label>
    	                          <input value={uploadDate} onChange={(e) => setUploadDate(e.target.value)} placeholder="YYYY-MM-DD" />
    	                        </div>
    	                        <div className="grid gap-1.5">
    	                          <label>范围</label>
    	                          <select value={uploadScope} onChange={(e) => setUploadScope(e.target.value as any)}>
    	                            <option value="public">公共作业</option>
    	                            <option value="class">班级作业</option>
    	                            <option value="student">私人作业</option>
    	                          </select>
    	                        </div>
    	                        <div className="grid gap-1.5">
    	                          <label>班级（班级作业必填）</label>
    	                          <input
    	                            value={uploadClassName}
    	                            onChange={(e) => setUploadClassName(e.target.value)}
    	                            placeholder="例如：高二2403班"
    	                          />
    	                        </div>
    	                        <div className="grid gap-1.5">
    	                          <label>学生编号（私人作业必填）</label>
    	                          <input
    	                            value={uploadStudentIds}
    	                            onChange={(e) => setUploadStudentIds(e.target.value)}
    	                            placeholder="例如：高二2403班_刘昊然"
    	                          />
    	                        </div>
    	                        <div className="grid gap-1.5">
    	                          <label>作业文件（文档/图片）</label>
    	                          <input
    	                            type="file"
    	                            multiple
    	                            accept="application/pdf,image/*,.md,.markdown,.tex"
    	                            onChange={(e) => setUploadFiles(Array.from(e.target.files || []))}
    	                          />
    	                        </div>
    	                        <div className="grid gap-1.5">
    	                          <label>答案文件（可选）</label>
    	                          <input
    	                            type="file"
    	                            multiple
    	                            accept="application/pdf,image/*,.md,.markdown,.tex"
    	                            onChange={(e) => setUploadAnswerFiles(Array.from(e.target.files || []))}
    	                          />
    	                        </div>
    	                      </div>
    	                      <button type="submit" className="border-none rounded-xl py-[10px] px-[14px] bg-accent text-white cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed" disabled={uploading}>
    	                        {uploading ? '上传中…' : '上传并开始解析'}
    	                      </button>
    	                    </form>
    	                    {uploadError && <div className="mt-[10px] p-[10px_12px] rounded-xl text-[12px] whitespace-pre-wrap overflow-x-auto bg-danger-soft text-danger">{uploadError}</div>}
    	                    {uploadStatus && <pre className="mt-[10px] p-[10px_12px] rounded-xl text-[12px] whitespace-pre-wrap overflow-x-auto bg-[#e8f7f2] text-[#0f766e]">{uploadStatus}</pre>}
    	                  </>
    	                ) : (
    	                  <>
    	                    <p className="m-0 mb-3 text-muted">上传考试试卷、标准答案（可选）与成绩表后，系统将生成考试数据与分析草稿。成绩表推荐电子表格（最稳）。</p>
    	                    <form className="upload-form grid gap-[10px]" onSubmit={handleUploadExam}>
    	                      <div className="grid gap-[10px] grid-cols-1">
    	                        <div className="grid gap-1.5">
    	                          <label>考试编号（可选）</label>
    	                          <input value={examId} onChange={(e) => setExamId(e.target.value)} placeholder="例如：EX2403_PHY" />
    	                        </div>
    	                        <div className="grid gap-1.5">
    	                          <label>日期（可选）</label>
    	                          <input value={examDate} onChange={(e) => setExamDate(e.target.value)} placeholder="YYYY-MM-DD" />
    	                        </div>
    	                        <div className="grid gap-1.5">
    	                          <label>班级（可选）</label>
    	                          <input
    	                            value={examClassName}
    	                            onChange={(e) => setExamClassName(e.target.value)}
    	                            placeholder="例如：高二2403班"
    	                          />
    	                        </div>
    	                        <div className="grid gap-1.5">
    	                          <label>试卷文件（必填）</label>
    	                          <input
    	                            type="file"
    	                            multiple
    	                            accept="application/pdf,image/*,.md,.markdown,.tex"
    	                            onChange={(e) => setExamPaperFiles(Array.from(e.target.files || []))}
    	                          />
    	                        </div>
    	                        <div className="grid gap-1.5">
    	                          <label>答案文件（可选）</label>
    	                          <input
    	                            type="file"
    	                            multiple
    	                            accept="application/pdf,image/*,.md,.markdown,.tex"
    	                            onChange={(e) => setExamAnswerFiles(Array.from(e.target.files || []))}
    	                          />
    	                        </div>
    	                        <div className="grid gap-1.5">
    	                          <label>成绩文件（必填）</label>
    	                          <input
    	                            type="file"
    	                            multiple
    	                            accept="application/pdf,image/*,.xls,.xlsx"
    	                            onChange={(e) => setExamScoreFiles(Array.from(e.target.files || []))}
    	                          />
    	                        </div>
    	                      </div>
    	                      <button type="submit" className="border-none rounded-xl py-[10px] px-[14px] bg-accent text-white cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed" disabled={examUploading}>
    	                        {examUploading ? '上传中…' : '上传并开始解析'}
    	                      </button>
    	                    </form>
    	                    {examUploadError && <div className="mt-[10px] p-[10px_12px] rounded-xl text-[12px] whitespace-pre-wrap overflow-x-auto bg-danger-soft text-danger">{examUploadError}</div>}
    	                    {examUploadStatus && <pre className="mt-[10px] p-[10px_12px] rounded-xl text-[12px] whitespace-pre-wrap overflow-x-auto bg-[#e8f7f2] text-[#0f766e]">{examUploadStatus}</pre>}
    	                  </>
    	                )}
    	              </>
    	            )}
    	          </section>
  )
}
