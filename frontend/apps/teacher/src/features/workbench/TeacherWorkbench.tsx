import { useState } from 'react'

type WorkbenchTab = 'skills' | 'memory' | 'workflow'
type ExamConflictLevel = 'strict' | 'standard' | 'lenient'

type TeacherWorkbenchProps = {
  skillsOpen: boolean
  setSkillsOpen: any
  workbenchTab: WorkbenchTab
  setWorkbenchTab: any
  activeSkillId: any
  activeWorkflowIndicator: any
  chooseSkill: any
  difficultyLabel: any
  difficultyOptions: readonly any[]
  draftActionError: any
  draftActionStatus: any
  draftError: any
  draftLoading: any
  draftPanelCollapsed: any
  draftSaving: any
  examClassName: any
  examConfirming: any
  examDate: any
  examDraft: any
  examDraftActionError: any
  examDraftActionStatus: any
  examDraftError: any
  examDraftLoading: any
  examDraftPanelCollapsed: any
  examDraftSaving: any
  examId: any
  examJobInfo: any
  examUploadError: any
  examUploadStatus: any
  examUploading: any
  favorites: any[]
  fetchAssignmentProgress: any
  fetchSkills: any
  filteredSkills: any[]
  formatDraftSummary: any
  formatExamDraftSummary: any
  formatExamJobSummary: any
  formatMissingRequirements: any
  formatProgressSummary: any
  formatUploadJobSummary: any
  handleConfirmExamUpload: any
  handleConfirmUpload: any
  handleUploadAssignment: any
  handleUploadExam: any
  insertInvocationTokenAtCursor: any
  insertPrompt: any
  memoryInsights: any
  memoryStatusFilter: any
  misconceptionsText: any
  normalizeDifficulty: any
  parseCommaList: any
  parseLineList: any
  progressAssignmentId: any
  progressData: any
  progressError: any
  progressLoading: any
  progressOnlyIncomplete: any
  progressPanelCollapsed: any
  proposalError: any
  proposalLoading: any
  proposals: any[]
  questionShowCount: any
  refreshMemoryInsights: any
  refreshMemoryProposals: any
  refreshWorkflowWorkbench: any
  saveDraft: any
  saveExamDraft: any
  scrollToWorkflowSection: any
  setComposerWarning: any
  setDraftPanelCollapsed: any
  setExamAnswerFiles: any
  setExamClassName: any
  setExamDate: any
  setExamDraftPanelCollapsed: any
  setExamId: any
  setExamPaperFiles: any
  setExamScoreFiles: any
  setMemoryStatusFilter: any
  setMisconceptionsDirty: any
  setMisconceptionsText: any
  setProgressAssignmentId: any
  setProgressOnlyIncomplete: any
  setProgressPanelCollapsed: any
  setQuestionShowCount: any
  setShowFavoritesOnly: any
  setSkillPinned: any
  setSkillQuery: any
  setUploadAnswerFiles: any
  setUploadAssignmentId: any
  setUploadCardCollapsed: any
  setUploadClassName: any
  setUploadDate: any
  setUploadFiles: any
  setUploadMode: any
  setUploadScope: any
  setUploadStudentIds: any
  showFavoritesOnly: any
  skillPinned: any
  skillQuery: any
  skillsError: any
  skillsLoading: any
  stopKeyPropagation: any
  toggleFavorite: any
  updateDraftQuestion: any
  updateDraftRequirement: any
  updateExamAnswerKeyText: any
  updateExamDraftMeta: any
  updateExamScoreSchemaSelectedCandidate: any
  updateExamQuestionField: any
  uploadAssignmentId: any
  uploadCardCollapsed: any
  uploadClassName: any
  uploadConfirming: any
  uploadDate: any
  uploadDraft: any
  uploadError: any
  uploadJobInfo: any
  uploadMode: any
  uploadScope: any
  uploadStatus: any
  uploadStudentIds: any
  uploading: any
}

export default function TeacherWorkbench(props: TeacherWorkbenchProps) {
  const [examConflictLevel, setExamConflictLevel] = useState<ExamConflictLevel>('standard')

  const {
    skillsOpen,
    setSkillsOpen,
    workbenchTab,
    setWorkbenchTab,
    activeSkillId,
    activeWorkflowIndicator,
    chooseSkill,
    difficultyLabel,
    difficultyOptions,
    draftActionError,
    draftActionStatus,
    draftError,
    draftLoading,
    draftPanelCollapsed,
    draftSaving,
    examClassName,
    examConfirming,
    examDate,
    examDraft,
    examDraftActionError,
    examDraftActionStatus,
    examDraftError,
    examDraftLoading,
    examDraftPanelCollapsed,
    examDraftSaving,
    examId,
    examJobInfo,
    examUploadError,
    examUploadStatus,
    examUploading,
    favorites,
    fetchAssignmentProgress,
    fetchSkills,
    filteredSkills,
    formatDraftSummary,
    formatExamDraftSummary,
    formatExamJobSummary,
    formatMissingRequirements,
    formatProgressSummary,
    formatUploadJobSummary,
    handleConfirmExamUpload,
    handleConfirmUpload,
    handleUploadAssignment,
    handleUploadExam,
    insertInvocationTokenAtCursor,
    insertPrompt,
    memoryInsights,
    memoryStatusFilter,
    misconceptionsText,
    normalizeDifficulty,
    parseCommaList,
    parseLineList,
    progressAssignmentId,
    progressData,
    progressError,
    progressLoading,
    progressOnlyIncomplete,
    progressPanelCollapsed,
    proposalError,
    proposalLoading,
    proposals,
    questionShowCount,
    refreshMemoryInsights,
    refreshMemoryProposals,
    refreshWorkflowWorkbench,
    saveDraft,
    saveExamDraft,
    scrollToWorkflowSection,
    setComposerWarning,
    setDraftPanelCollapsed,
    setExamAnswerFiles,
    setExamClassName,
    setExamDate,
    setExamDraftPanelCollapsed,
    setExamId,
    setExamPaperFiles,
    setExamScoreFiles,
    setMemoryStatusFilter,
    setMisconceptionsDirty,
    setMisconceptionsText,
    setProgressAssignmentId,
    setProgressOnlyIncomplete,
    setProgressPanelCollapsed,
    setQuestionShowCount,
    setShowFavoritesOnly,
    setSkillPinned,
    setSkillQuery,
    setUploadAnswerFiles,
    setUploadAssignmentId,
    setUploadCardCollapsed,
    setUploadClassName,
    setUploadDate,
    setUploadFiles,
    setUploadMode,
    setUploadScope,
    setUploadStudentIds,
    showFavoritesOnly,
    skillPinned,
    skillQuery,
    skillsError,
    skillsLoading,
    stopKeyPropagation,
    toggleFavorite,
    updateDraftQuestion,
    updateDraftRequirement,
    updateExamAnswerKeyText,
    updateExamDraftMeta,
    updateExamScoreSchemaSelectedCandidate,
    updateExamQuestionField,
    uploadAssignmentId,
    uploadCardCollapsed,
    uploadClassName,
    uploadConfirming,
    uploadDate,
    uploadDraft,
    uploadError,
    uploadJobInfo,
    uploadMode,
    uploadScope,
    uploadStatus,
    uploadStudentIds,
    uploading,
  } = props

  const examConflictThreshold =
    examConflictLevel === 'strict'
      ? 25
      : examConflictLevel === 'lenient'
        ? 8
        : 15
  const examConflictLevelLabel =
    examConflictLevel === 'strict'
      ? '严格'
      : examConflictLevel === 'lenient'
        ? '宽松'
        : '标准'

  const examNeedsConfirm = Boolean(examDraft?.needs_confirm || examDraft?.score_schema?.needs_confirm)
  const examSubjectSchema = examDraft?.score_schema?.subject || {}
  const examCandidateColumns = Array.isArray(examSubjectSchema?.candidate_columns) ? examSubjectSchema.candidate_columns : []
  const examSelectedCandidateId = String(examSubjectSchema?.selected_candidate_id || '')
  const examRequestedCandidateId = String(examSubjectSchema?.requested_candidate_id || '')
  const examSelectedCandidateAvailable = examSubjectSchema?.selected_candidate_available !== false
  const showExamCandidateCard = Boolean(examNeedsConfirm || examCandidateColumns.length)
  const examRecommendedCandidate = (() => {
    if (!examCandidateColumns.length) return null
    const typeWeight = (value: string) => {
      if (value === 'subject_pair') return 30
      if (value === 'direct_physics') return 20
      if (value === 'chaos_text_scan') return 6
      return 0
    }
    const sorted = [...examCandidateColumns]
      .map((candidate: any) => {
        const rowsConsidered = Number(candidate?.rows_considered || 0)
        const rowsParsed = Number(candidate?.rows_parsed || 0)
        const rowsInvalid = Number(candidate?.rows_invalid || 0)
        const parseRate = rowsConsidered > 0 ? rowsParsed / rowsConsidered : 0
        const candidateType = String(candidate?.type || '')
        const score = (rowsParsed * 100) + (parseRate * 40) - (rowsInvalid * 12) + typeWeight(candidateType)
        return {
          candidate,
          candidateId: String(candidate?.candidate_id || ''),
          rowsConsidered,
          rowsParsed,
          rowsInvalid,
          parseRate,
          candidateType,
          score,
        }
      })
      .filter((item) => item.candidateId)
      .sort((a, b) => b.score - a.score || b.rowsParsed - a.rowsParsed || a.rowsInvalid - b.rowsInvalid)
    return sorted[0] || null
  })()
  const examConflictStudents = (() => {
    if (!examCandidateColumns.length) return []
    const byStudent = new Map<string, { studentId: string; studentName: string; entries: Array<{ candidateId: string; score: number }> }>()
    for (const candidate of examCandidateColumns) {
      const candidateId = String(candidate?.candidate_id || '')
      if (!candidateId) continue
      const samples = Array.isArray(candidate?.sample_rows) ? candidate.sample_rows : []
      for (const row of samples) {
        if (!row || row?.status !== 'parsed') continue
        const scoreRaw = Number(row?.score)
        if (!Number.isFinite(scoreRaw)) continue
        const studentId = String(row?.student_id || '').trim()
        const studentName = String(row?.student_name || '').trim()
        const key = studentId || studentName
        if (!key) continue
        const bucket = byStudent.get(key) || { studentId, studentName, entries: [] }
        bucket.entries.push({ candidateId, score: scoreRaw })
        byStudent.set(key, bucket)
      }
    }
    const conflicts: Array<{
      studentId: string
      studentName: string
      minScore: number
      maxScore: number
      spread: number
      entries: Array<{ candidateId: string; score: number }>
    }> = []
    for (const item of byStudent.values()) {
      const uniqueEntries: Array<{ candidateId: string; score: number }> = []
      const seenCandidates = new Set<string>()
      for (const entry of item.entries) {
        if (!entry.candidateId || seenCandidates.has(entry.candidateId)) continue
        seenCandidates.add(entry.candidateId)
        uniqueEntries.push(entry)
      }
      if (uniqueEntries.length < 2) continue
      const scores = uniqueEntries.map((entry) => entry.score)
      const minScore = Math.min(...scores)
      const maxScore = Math.max(...scores)
      const spread = maxScore - minScore
      if (spread < examConflictThreshold) continue
      conflicts.push({
        studentId: item.studentId,
        studentName: item.studentName,
        minScore,
        maxScore,
        spread,
        entries: uniqueEntries.sort((a, b) => b.score - a.score),
      })
    }
    return conflicts.sort((a, b) => b.spread - a.spread).slice(0, 8)
  })()

  return (
              <aside className={`skills-panel ${skillsOpen ? 'open' : ''}`}>
                <div className="skills-header">
                  <h3>工作台</h3>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button
                      className="ghost"
                      onClick={() => {
                        if (workbenchTab === 'skills') {
                          void fetchSkills()
                        } else if (workbenchTab === 'memory') {
                          void refreshMemoryProposals()
                          void refreshMemoryInsights()
                        } else {
                          refreshWorkflowWorkbench()
                        }
                      }}
                      disabled={
                        workbenchTab === 'skills'
                          ? skillsLoading
                          : workbenchTab === 'memory'
                            ? proposalLoading
                            : progressLoading || uploading || examUploading
                      }
                    >
                      刷新
                    </button>
                    <button className="ghost" onClick={() => setSkillsOpen(false)}>
                      收起
                    </button>
                  </div>
                </div>
                <div className="view-switch workbench-switch">
                  <button type="button" className={workbenchTab === 'skills' ? 'active' : ''} onClick={() => setWorkbenchTab('skills')}>
                    技能
                  </button>
                  <button type="button" className={workbenchTab === 'memory' ? 'active' : ''} onClick={() => setWorkbenchTab('memory')}>
                    自动记忆
                  </button>
                  <button type="button" className={workbenchTab === 'workflow' ? 'active' : ''} onClick={() => setWorkbenchTab('workflow')}>
                    工作流
                  </button>
                </div>
                {workbenchTab === 'skills' ? (
                  <>
                    <div className="skills-tools">
                      <div className="skills-tools-search">
                        <input
                          value={skillQuery}
                          onChange={(e) => setSkillQuery(e.target.value)}
                          placeholder="搜索技能"
                        />
                      </div>
                      <div className="skills-tools-actions">
                        <button
                          type="button"
                          className="ghost"
                          disabled={!skillPinned}
                          onClick={() => {
                            setSkillPinned(false)
                            setComposerWarning('已切换到自动技能路由（未显式指定时由后端自动选择）。')
                          }}
                        >
                          使用自动路由
                        </button>
                        <label className="toggle">
                          <input
                            type="checkbox"
                            checked={showFavoritesOnly}
                            onChange={(e) => setShowFavoritesOnly(e.target.checked)}
                          />
                          只看收藏
                        </label>
                      </div>
                    </div>
                    {skillsLoading && <div className="skills-status">正在加载技能...</div>}
                    {skillsError && <div className="skills-status err">{skillsError}</div>}
                    <div className="skills-body">
                      {filteredSkills.map((skill) => (
                        <div key={skill.id} className={`skill-card ${skillPinned && skill.id === activeSkillId ? 'active' : ''}`}>
                          <div className="skill-title">
                            <div>
                              <strong>{skill.title}</strong>
                            </div>
                            <button
                              type="button"
                              className={`fav ${favorites.includes(skill.id) ? 'active' : ''}`}
                              onClick={() => toggleFavorite(skill.id)}
                              aria-label="收藏技能"
                            >
                              {favorites.includes(skill.id) ? '★' : '☆'}
                            </button>
                          </div>
                          <p>{skill.desc}</p>
                          <div className="skill-actions">
                            <button
                              type="button"
                              onClick={() => {
                                chooseSkill(skill.id, true)
                                setComposerWarning('')
                              }}
                            >
                              设为当前
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                chooseSkill(skill.id, true)
                                insertInvocationTokenAtCursor('skill', skill.id)
                              }}
                            >
                              插入 $
                            </button>
                          </div>
                          <div className="skill-prompts">
                            {skill.prompts.map((prompt: any) => (
                              <button
                                key={prompt}
                                type="button"
                                onClick={() => {
                                  chooseSkill(skill.id, true)
                                  insertPrompt(prompt)
                                }}
                              >
                                使用模板
                              </button>
                            ))}
                          </div>
                          <div className="skill-examples">
                            {skill.examples.map((ex: any) => (
                              <button
                                key={ex}
                                type="button"
                                onClick={() => {
                                  chooseSkill(skill.id, true)
                                  insertPrompt(ex)
                                }}
                              >
                                {ex}
                              </button>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </>
                ) : workbenchTab === 'workflow' ? (
                  <section className="memory-panel workbench-memory workbench-workflow">
                    <div className="history-header">
                      <strong>作业流程控制</strong>
                    </div>
                    <div className="workflow-summary-card">
                      <div className="segmented">
                        <button type="button" className={uploadMode === 'assignment' ? 'active' : ''} onClick={() => setUploadMode('assignment')}>
                          作业
                        </button>
                        <button type="button" className={uploadMode === 'exam' ? 'active' : ''} onClick={() => setUploadMode('exam')}>
                          考试
                        </button>
                      </div>
                      <div className="workflow-headline">
                        <div className="muted">当前流程状态</div>
                        <span className={`workflow-chip ${activeWorkflowIndicator.tone}`}>{activeWorkflowIndicator.label}</span>
                      </div>
                      <div className="workflow-steps">
                        {activeWorkflowIndicator.steps.map((step: any) => (
                          <div key={step.key} className={`workflow-step ${step.state}`}>
                            <span className="workflow-step-dot" />
                            <span className="workflow-step-label">{step.label}</span>
                          </div>
                        ))}
                      </div>
                      <div className="workflow-status">
                        {uploadMode === 'assignment'
                          ? formatUploadJobSummary(uploadJobInfo, uploadAssignmentId.trim())
                          : formatExamJobSummary(examJobInfo, examId.trim())}
                      </div>
                      <div className="workflow-actions">
                        <button type="button" className="ghost" onClick={() => scrollToWorkflowSection('workflow-upload-section')}>
                          定位上传区
                        </button>
                        {uploadMode === 'assignment' ? (
                          <button type="button" className="ghost" onClick={() => scrollToWorkflowSection('workflow-assignment-draft-section')}>
                            定位作业草稿
                          </button>
                        ) : (
                          <button type="button" className="ghost" onClick={() => scrollToWorkflowSection('workflow-exam-draft-section')}>
                            定位考试草稿
                          </button>
                        )}
                        <button type="button" className="ghost" onClick={refreshWorkflowWorkbench}>
                          刷新状态
                        </button>
                      </div>
                    </div>
                    {uploadMode === 'assignment' ? (
                      <div className="workflow-summary-card">
                        <div className="muted">作业完成情况</div>
                        <div className="workflow-status">{formatProgressSummary(progressData, progressAssignmentId)}</div>
                        <div className="workflow-actions">
                          <button type="button" className="ghost" onClick={() => scrollToWorkflowSection('workflow-progress-section')}>
                            定位完成情况
                          </button>
                          <button type="button" className="ghost" disabled={progressLoading} onClick={() => void fetchAssignmentProgress()}>
                            {progressLoading ? '加载中…' : '刷新完成率'}
                          </button>
                        </div>
                      </div>
                    ) : null}
              <section id="workflow-upload-section" className={`upload-card ${uploadCardCollapsed ? 'collapsed' : ''}`}>
    	            <div className="panel-header">
    	              <div className="panel-title">
    	                <h3>{uploadMode === 'assignment' ? '上传作业文件（文档 / 图片）' : '上传考试文件（试卷 + 成绩表）'}</h3>
    	                <div className="segmented">
    	                  <button
    	                    type="button"
    	                    className={uploadMode === 'assignment' ? 'active' : ''}
    	                    onClick={() => setUploadMode('assignment')}
    	                  >
    	                    作业
    	                  </button>
    	                  <button type="button" className={uploadMode === 'exam' ? 'active' : ''} onClick={() => setUploadMode('exam')}>
    	                    考试
    	                  </button>
    	                </div>
    	              </div>
    	              {uploadCardCollapsed ? (
    	                <div
    	                  className="panel-summary"
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
    	                    <p>上传后将在后台解析题目与答案，并生成作业 8 点描述。解析完成后需确认创建作业。</p>
    	                    <form className="upload-form" onSubmit={handleUploadAssignment}>
    	                      <div className="upload-grid">
    	                        <div className="upload-field">
    	                          <label>作业编号</label>
    	                          <input
    	                            value={uploadAssignmentId}
    	                            onChange={(e) => setUploadAssignmentId(e.target.value)}
    	                            placeholder="例如：HW-2026-02-05"
    	                          />
    	                        </div>
    	                        <div className="upload-field">
    	                          <label>日期（可选）</label>
    	                          <input value={uploadDate} onChange={(e) => setUploadDate(e.target.value)} placeholder="YYYY-MM-DD" />
    	                        </div>
    	                        <div className="upload-field">
    	                          <label>范围</label>
    	                          <select value={uploadScope} onChange={(e) => setUploadScope(e.target.value as any)}>
    	                            <option value="public">公共作业</option>
    	                            <option value="class">班级作业</option>
    	                            <option value="student">私人作业</option>
    	                          </select>
    	                        </div>
    	                        <div className="upload-field">
    	                          <label>班级（班级作业必填）</label>
    	                          <input
    	                            value={uploadClassName}
    	                            onChange={(e) => setUploadClassName(e.target.value)}
    	                            placeholder="例如：高二2403班"
    	                          />
    	                        </div>
    	                        <div className="upload-field">
    	                          <label>学生编号（私人作业必填）</label>
    	                          <input
    	                            value={uploadStudentIds}
    	                            onChange={(e) => setUploadStudentIds(e.target.value)}
    	                            placeholder="例如：高二2403班_刘昊然"
    	                          />
    	                        </div>
    	                        <div className="upload-field">
    	                          <label>作业文件（文档/图片）</label>
    	                          <input
    	                            type="file"
    	                            multiple
    	                            accept="application/pdf,image/*,.md,.markdown,.tex"
    	                            onChange={(e) => setUploadFiles(Array.from(e.target.files || []))}
    	                          />
    	                        </div>
    	                        <div className="upload-field">
    	                          <label>答案文件（可选）</label>
    	                          <input
    	                            type="file"
    	                            multiple
    	                            accept="application/pdf,image/*,.md,.markdown,.tex"
    	                            onChange={(e) => setUploadAnswerFiles(Array.from(e.target.files || []))}
    	                          />
    	                        </div>
    	                      </div>
    	                      <button type="submit" disabled={uploading}>
    	                        {uploading ? '上传中…' : '上传并开始解析'}
    	                      </button>
    	                    </form>
    	                    {uploadError && <div className="status err">{uploadError}</div>}
    	                    {uploadStatus && <pre className="status ok">{uploadStatus}</pre>}
    	                  </>
    	                ) : (
    	                  <>
    	                    <p>上传考试试卷、标准答案（可选）与成绩表后，系统将生成考试数据与分析草稿。成绩表推荐电子表格（最稳）。</p>
    	                    <form className="upload-form" onSubmit={handleUploadExam}>
    	                      <div className="upload-grid">
    	                        <div className="upload-field">
    	                          <label>考试编号（可选）</label>
    	                          <input value={examId} onChange={(e) => setExamId(e.target.value)} placeholder="例如：EX2403_PHY" />
    	                        </div>
    	                        <div className="upload-field">
    	                          <label>日期（可选）</label>
    	                          <input value={examDate} onChange={(e) => setExamDate(e.target.value)} placeholder="YYYY-MM-DD" />
    	                        </div>
    	                        <div className="upload-field">
    	                          <label>班级（可选）</label>
    	                          <input
    	                            value={examClassName}
    	                            onChange={(e) => setExamClassName(e.target.value)}
    	                            placeholder="例如：高二2403班"
    	                          />
    	                        </div>
    	                        <div className="upload-field">
    	                          <label>试卷文件（必填）</label>
    	                          <input
    	                            type="file"
    	                            multiple
    	                            accept="application/pdf,image/*,.md,.markdown,.tex"
    	                            onChange={(e) => setExamPaperFiles(Array.from(e.target.files || []))}
    	                          />
    	                        </div>
    	                        <div className="upload-field">
    	                          <label>答案文件（可选）</label>
    	                          <input
    	                            type="file"
    	                            multiple
    	                            accept="application/pdf,image/*,.md,.markdown,.tex"
    	                            onChange={(e) => setExamAnswerFiles(Array.from(e.target.files || []))}
    	                          />
    	                        </div>
    	                        <div className="upload-field">
    	                          <label>成绩文件（必填）</label>
    	                          <input
    	                            type="file"
    	                            multiple
    	                            accept="application/pdf,image/*,.xls,.xlsx"
    	                            onChange={(e) => setExamScoreFiles(Array.from(e.target.files || []))}
    	                          />
    	                        </div>
    	                      </div>
    	                      <button type="submit" disabled={examUploading}>
    	                        {examUploading ? '上传中…' : '上传并开始解析'}
    	                      </button>
    	                    </form>
    	                    {examUploadError && <div className="status err">{examUploadError}</div>}
    	                    {examUploadStatus && <pre className="status ok">{examUploadStatus}</pre>}
    	                  </>
    	                )}
    	              </>
    	            )}
    	          </section>
    
    	          {uploadMode === 'assignment' && (
    	            <section id="workflow-progress-section" className={`draft-panel ${progressPanelCollapsed ? 'collapsed' : ''}`}>
    	              <div className="panel-header">
    	                <h3>作业完成情况</h3>
    	                {progressPanelCollapsed ? (
    	                  <div
    	                    className="panel-summary"
    	                    title={formatProgressSummary(progressData, progressAssignmentId)}
    	                  >
    	                    {formatProgressSummary(progressData, progressAssignmentId)}
    	                  </div>
    	                ) : null}
	    	                <button type="button" className="ghost" onClick={() => setProgressPanelCollapsed((v: boolean) => !v)}>
    	                  {progressPanelCollapsed ? '展开' : '收起'}
    	                </button>
    	              </div>
    	              {progressPanelCollapsed ? null : (
    	                <>
    	                  <div className="progress-toolbar">
    	                    <div className="upload-field">
    	                      <label>作业编号</label>
    	                      <input
    	                        value={progressAssignmentId}
    	                        onChange={(e) => setProgressAssignmentId(e.target.value)}
    	                        placeholder="例如：A2403_2026-02-04"
    	                      />
    	                    </div>
    	                    <div className="progress-toolbar-actions">
    	                      <label className="toggle">
    	                        <input
    	                          type="checkbox"
    	                          checked={progressOnlyIncomplete}
    	                          onChange={(e) => setProgressOnlyIncomplete(e.target.checked)}
    	                        />
    	                        只看未完成
    	                      </label>
    	                      <button
    	                        type="button"
    	                        className="secondary-btn"
    	                        disabled={progressLoading}
    	                        onClick={() => void fetchAssignmentProgress()}
    	                      >
    	                        {progressLoading ? '加载中…' : '刷新'}
    	                      </button>
    	                    </div>
    	                  </div>
    
    	                  {progressError && <div className="status err">{progressError}</div>}
    	                  {progressData && (
    	                    <div className="draft-meta">
    	                      <div>作业编号：{progressData.assignment_id}</div>
    	                      <div>日期：{String(progressData.date || '') || '（未设置）'}</div>
    	                      <div>
    	                        应交：{progressData.counts?.expected ?? progressData.expected_count ?? 0} · 完成：
    	                        {progressData.counts?.completed ?? 0} · 讨论通过：
    	                        {progressData.counts?.discussion_pass ?? 0} · 已评分：
    	                        {progressData.counts?.submitted ?? 0}
    	                        {progressData.counts?.overdue ? ` · 逾期：${progressData.counts.overdue}` : ''}
    	                      </div>
    	                      <div>截止：{progressData.due_at ? progressData.due_at : '永不截止'}</div>
    	                    </div>
    	                  )}
    
    	                  {progressData?.students && progressData.students.length > 0 && (
    	                    <div className="progress-list">
	    	                      {(progressOnlyIncomplete
	    	                        ? progressData.students.filter((s: any) => !s.complete)
    	                        : progressData.students
	    	                      ).map((s: any) => {
    	                        const attempts = s.submission?.attempts ?? 0
    	                        const best = s.submission?.best as any
    	                        const graded = best
    	                          ? `得分${best.score_earned ?? 0}`
    	                          : attempts
    	                            ? `已提交${attempts}次（未评分）`
    	                            : '未提交'
    	                        const discussion = s.discussion?.pass ? '讨论通过' : '讨论未完成'
    	                        const overdue = s.overdue ? ' · 逾期' : ''
    	                        const name = [s.class_name, s.student_name].filter(Boolean).join(' ')
    	                        return (
    	                          <div key={s.student_id} className={`progress-row ${s.complete ? 'ok' : 'todo'}`}>
    	                            <div className="progress-main">
    	                              <strong>{s.student_id}</strong>
    	                              {name ? <span className="muted"> {name}</span> : null}
    	                            </div>
    	                            <div className="progress-sub">
    	                              {discussion} · {graded}
    	                              {overdue}
    	                            </div>
    	                          </div>
    	                        )
    	                      })}
    	                    </div>
    	                  )}
    	                </>
    	              )}
    	            </section>
    	          )}
    
    	          {uploadMode === 'exam' && examDraftLoading && (
    	            <section className="draft-panel">
    	              <h3>考试解析结果（审核/修改）</h3>
    	              <div className="status ok">草稿加载中…</div>
    	            </section>
    	          )}
    
    	          {uploadMode === 'exam' && examDraftError && (
    	            <section className="draft-panel">
    	              <h3>考试解析结果（审核/修改）</h3>
    	              <div className="status err">{examDraftError}</div>
    	            </section>
    	          )}
    
    	          {uploadMode === 'exam' && examDraft && (
    	            <section id="workflow-exam-draft-section" className={`draft-panel ${examDraftPanelCollapsed ? 'collapsed' : ''}`}>
    	              <div className="panel-header">
    	                <h3>考试解析结果（审核/修改）</h3>
    	                {examDraftPanelCollapsed ? (
    	                  <div className="panel-summary" title={formatExamDraftSummary(examDraft, examJobInfo)}>
    	                    {formatExamDraftSummary(examDraft, examJobInfo)}
    	                  </div>
    	                ) : null}
	    	                <button type="button" className="ghost" onClick={() => setExamDraftPanelCollapsed((v: boolean) => !v)}>
    	                  {examDraftPanelCollapsed ? '展开' : '收起'}
    	                </button>
    	              </div>
    	              {examDraftPanelCollapsed ? null : (
    	                <>
    	                  <div className="draft-meta">
    	                    <div>考试编号：{examDraft.exam_id}</div>
    	                    <div>日期：{String(examDraft.meta?.date || examDraft.date || '') || '（未设置）'}</div>
    	                    {examDraft.meta?.class_name ? <div>班级：{String(examDraft.meta.class_name)}</div> : null}
    	                    {examDraft.answer_files?.length ? <div>答案文件：{examDraft.answer_files.length} 份</div> : null}
    	                    {examDraft.answer_key?.count !== undefined && examDraft.answer_key?.count !== 0 ? (
    	                      <div>解析到答案：{String(examDraft.answer_key.count)} 条</div>
    	                    ) : null}
    	                    {examDraft.counts?.students !== undefined ? <div>学生数：{examDraft.counts.students}</div> : null}
    	                    {examDraft.scoring?.status ? (
    	                      <div>
    	                        评分状态：
    	                        {{
    	                          scored: '已评分',
    	                          partial: '部分已评分',
    	                          unscored: '未评分',
    	                        }[String(examDraft.scoring.status)] || String(examDraft.scoring.status)}
    	                        {examDraft.scoring?.students_scored !== undefined && examDraft.scoring?.students_total !== undefined
    	                          ? `（已评分学生 ${examDraft.scoring.students_scored}/${examDraft.scoring.students_total}）`
    	                          : ''}
    	                      </div>
    	                    ) : null}
    	                    {Array.isArray(examDraft.scoring?.default_max_score_qids) && examDraft.scoring.default_max_score_qids.length ? (
    	                      <div className="muted">
    	                        提示：有 {examDraft.scoring.default_max_score_qids.length} 题缺少满分，系统已默认按 1 分/题 评分（建议核对题目满分）。
    	                      </div>
    	                    ) : null}
    	                    {examDraft.counts?.questions !== undefined ? <div>题目数：{examDraft.counts.questions}</div> : null}
    	                    {examDraft.totals_summary?.avg_total !== undefined ? <div>平均分：{examDraft.totals_summary.avg_total}</div> : null}
    	                    {examDraft.totals_summary?.median_total !== undefined ? <div>中位数：{examDraft.totals_summary.median_total}</div> : null}
    	                    {examDraft.totals_summary?.max_total_observed !== undefined ? (
    	                      <div>最高分(观测)：{examDraft.totals_summary.max_total_observed}</div>
    	                    ) : null}
    	                  </div>
    
	                  {examDraftActionError && <div className="status err">{examDraftActionError}</div>}
	                  {examDraftActionStatus && <pre className="status ok">{examDraftActionStatus}</pre>}

	                  {examNeedsConfirm ? (
	                    <div className="status err">
	                      当前成绩映射置信度不足，请先在“物理分映射确认”里选择映射列并保存草稿，等待重新解析完成后再创建考试。
	                    </div>
	                  ) : null}
    
    	                  <div className="draft-actions">
    	                    <button
    	                      type="button"
    	                      className="secondary-btn"
    	                      onClick={() => {
    	                        if (!examDraft) return
    	                        void saveExamDraft(examDraft).catch(() => {})
    	                      }}
    	                      disabled={examDraftSaving}
    	                    >
    	                      {examDraftSaving ? '保存中…' : '保存草稿'}
    	                    </button>
	                    <button
	                      type="button"
	                      onClick={handleConfirmExamUpload}
	                      disabled={examConfirming || examDraftSaving || examNeedsConfirm || !examJobInfo || examJobInfo.status !== 'done'}
	                      title={
	                        examNeedsConfirm
	                          ? '请先确认物理分映射并保存草稿'
	                          : examJobInfo && examJobInfo.status !== 'done'
	                            ? '解析未完成，暂不可创建'
	                            : ''
	                      }
	                    >
    	                      {examConfirming
    	                        ? examJobInfo && (examJobInfo.status as any) === 'confirming'
    	                          ? `创建中…${examJobInfo.progress ?? 0}%`
    	                          : '创建中…'
    	                        : examJobInfo && examJobInfo.status === 'confirmed'
    	                          ? '已创建'
    	                          : '创建考试'}
    	                    </button>
    	                  </div>
    
	                  <div className="draft-grid">
	                    {showExamCandidateCard ? (
	                      <div className="draft-card">
	                        <h4>物理分映射确认</h4>
	                        <div className="draft-form">
	                          <label>映射候选列</label>
	                          {examCandidateColumns.length ? (
	                            <>
	                              <select
	                                value={examSelectedCandidateId}
	                                onChange={(e) => updateExamScoreSchemaSelectedCandidate(e.target.value)}
	                                onKeyDown={stopKeyPropagation}
	                              >
	                                <option value="">请选择物理分映射列</option>
	                                {examCandidateColumns.map((candidate: any, idx: number) => {
	                                  const candidateId = String(candidate?.candidate_id || '')
	                                  if (!candidateId) return null
	                                  const kindLabel =
	                                    candidate?.type === 'subject_pair'
	                                      ? '科目+分数列'
	                                      : candidate?.type === 'direct_physics'
	                                        ? '物理分列'
	                                        : candidate?.type === 'chaos_text_scan'
	                                          ? '混乱文本兜底'
	                                          : String(candidate?.type || '未知类型')
	                                  const locationLabel = [
	                                    candidate?.file ? `文件 ${candidate.file}` : '',
	                                    candidate?.subject_header ? `科目列 ${candidate.subject_header}` : '',
	                                    candidate?.score_header ? `分数列 ${candidate.score_header}` : '',
	                                    (candidate?.rows_parsed !== undefined || candidate?.rows_considered !== undefined)
	                                      ? `命中 ${candidate?.rows_parsed ?? 0}/${candidate?.rows_considered ?? 0}`
	                                      : '',
	                                  ]
	                                    .filter(Boolean)
	                                    .join(' · ')
	                                  return (
	                                    <option key={`${candidateId}-${idx}`} value={candidateId}>
	                                      {`${candidateId}｜${kindLabel}${locationLabel ? `｜${locationLabel}` : ''}`}
	                                    </option>
	                                  )
	                                })}
	                              </select>
	                              {examRecommendedCandidate ? (
	                                <div className="draft-actions" style={{ marginTop: 8 }}>
	                                  <button
	                                    type="button"
	                                    className="secondary-btn"
	                                    onClick={() => updateExamScoreSchemaSelectedCandidate(examRecommendedCandidate.candidateId)}
	                                    disabled={examSelectedCandidateId === examRecommendedCandidate.candidateId}
	                                  >
	                                    {examSelectedCandidateId === examRecommendedCandidate.candidateId
	                                      ? '已使用推荐映射'
	                                      : '一键使用推荐映射'}
	                                  </button>
	                                </div>
	                              ) : null}
	                            </>
	                          ) : (
	                            <div className="status err">未检测到可确认的物理分映射列。建议更换更规范的成绩表后重试。</div>
	                          )}
	                        </div>
                        {examRecommendedCandidate ? (
                          <div className="status ok">
                            推荐映射：{examRecommendedCandidate.candidateId}（命中 {examRecommendedCandidate.rowsParsed}/
                            {examRecommendedCandidate.rowsConsidered}，无效 {examRecommendedCandidate.rowsInvalid}）
                          </div>
                        ) : null}
                        {examCandidateColumns.length > 1 ? (
                          <div className="draft-form" style={{ marginTop: 8 }}>
                            <label>冲突筛选强度</label>
                            <select
                              value={examConflictLevel}
                              onChange={(e) => {
                                const raw = String(e.target.value || '')
                                const nextLevel: ExamConflictLevel =
                                  raw === 'strict' || raw === 'lenient' ? raw : 'standard'
                                setExamConflictLevel(nextLevel)
                              }}
                              onKeyDown={stopKeyPropagation}
                            >
                              <option value="strict">严格（分差≥25 才提示）</option>
                              <option value="standard">标准（分差≥15 提示）</option>
                              <option value="lenient">宽松（分差≥8 提示）</option>
                            </select>
                            <div className="muted">当前模式：{examConflictLevelLabel}（阈值 {examConflictThreshold} 分）</div>
                          </div>
                        ) : null}
                        {examConflictStudents.length ? (
                          <details style={{ marginTop: 8 }}>
                            <summary className="muted">查看样本冲突学生（候选列分差较大）</summary>
	                            <div className="exam-candidate-conflicts">
	                              {examConflictStudents.map((item, idx) => {
	                                const studentLabel = [item.studentName, item.studentId ? `(${item.studentId})` : '']
	                                  .filter(Boolean)
	                                  .join(' ')
	                                const detailLabel = item.entries.map((entry) => `${entry.candidateId}=${entry.score}`).join('；')
	                                return (
	                                  <div key={`conflict-${idx}-${item.studentId || item.studentName}`} className="exam-candidate-conflict-row">
	                                    <strong>{studentLabel || `样本学生 ${idx + 1}`}</strong>
	                                    <span className="status-tag err">分差 {item.spread.toFixed(1)}</span>
	                                    <span className="muted">{detailLabel}</span>
	                                  </div>
	                                )
	                              })}
	                            </div>
	                          </details>
	                        ) : null}
	                        {examRequestedCandidateId && !examSelectedCandidateAvailable ? (
	                          <div className="status err">上次选择的映射列在当前文件中不可用，已回退自动匹配，请重新选择。</div>
	                        ) : null}
	                        {examSelectedCandidateId ? (
	                          <div className="status ok">当前已选映射：{examSelectedCandidateId}</div>
	                        ) : null}
	                        <div className="muted" style={{ marginTop: 8 }}>
	                          选择后点击“保存草稿”，系统会按所选映射重跑解析；重跑完成后可创建考试。
	                        </div>
	                        {Array.isArray(examSubjectSchema?.unresolved_students) && examSubjectSchema.unresolved_students.length ? (
	                          <div className="muted" style={{ marginTop: 4 }}>
	                            未解析到物理分学生：{examSubjectSchema.unresolved_students.length} 人（将按高置信结果保留）。
	                          </div>
	                        ) : null}
	                        {examSelectedCandidateId ? (
	                          <details style={{ marginTop: 8 }}>
	                            <summary className="muted">查看当前映射样本预览（最多 5 行）</summary>
	                            {(() => {
	                              const selected = examCandidateColumns.find(
	                                (candidate: any) => String(candidate?.candidate_id || '') === examSelectedCandidateId,
	                              )
	                              const rows = Array.isArray(selected?.sample_rows) ? selected.sample_rows : []
	                              if (!rows.length) return <div className="muted">当前映射暂无样本行。</div>
	                              return (
	                                <div className="exam-candidate-samples">
	                                  {rows.map((row: any, rowIdx: number) => {
	                                    const label = [
	                                      row?.class_name ? String(row.class_name) : '',
	                                      row?.student_name ? String(row.student_name) : '',
	                                      row?.student_id ? `(${String(row.student_id)})` : '',
	                                    ]
	                                      .filter(Boolean)
	                                      .join(' ')
	                                    const statusLabel = row?.status === 'parsed' ? '可解析' : '无效'
	                                    const scoreLabel = row?.score !== undefined && row?.score !== null ? ` → ${row.score}` : ''
	                                    return (
	                                      <div key={`${examSelectedCandidateId}-sample-${rowIdx}`} className="exam-candidate-sample-row">
	                                        <strong>{label || `样本 ${rowIdx + 1}`}</strong>
	                                        <span className={row?.status === 'parsed' ? 'status-tag ok' : 'status-tag err'}>{statusLabel}</span>
	                                        <span className="muted">原始值：{String(row?.raw_value || '（空）')}{scoreLabel}</span>
	                                      </div>
	                                    )
	                                  })}
	                                </div>
	                              )
	                            })()}
	                          </details>
	                        ) : null}
	                        {(examSubjectSchema?.coverage !== undefined || examDraft?.score_schema?.confidence !== undefined) ? (
	                          <div className="muted" style={{ marginTop: 4 }}>
	                            当前覆盖率：{examSubjectSchema?.coverage ?? '-'}；置信度：{examDraft?.score_schema?.confidence ?? '-'}。
	                          </div>
	                        ) : null}
	                      </div>
	                    ) : null}
	                    <div className="draft-card">
	                      <h4>考试信息（可编辑）</h4>
    	                      <div className="draft-form">
    	                        <label>日期（YYYY-MM-DD）</label>
    	                        <input
    	                          value={String(examDraft.meta?.date || '')}
    	                          onChange={(e) => updateExamDraftMeta('date', e.target.value)}
    	                        />
    	                        <label>班级</label>
    	                        <input
    	                          value={String(examDraft.meta?.class_name || '')}
    	                          onChange={(e) => updateExamDraftMeta('class_name', e.target.value)}
    	                        />
    	                      </div>
    	                    </div>
    	                    <div className="draft-card">
    	                      <h4>题目满分（可编辑）</h4>
    	                      <div className="exam-question-list">
	    	                        {(examDraft.questions || []).map((q: any, idx: number) => (
    	                          <div className="exam-question-row" key={`${q.question_id || 'q'}-${idx}`}>
    	                            <div className="exam-question-id">{q.question_id || `Q${idx + 1}`}</div>
    	                            <div className="exam-question-no">{q.question_no ? `题号 ${q.question_no}` : ''}</div>
    	                            <input
    	                              type="number"
    	                              min={0}
    	                              step={0.5}
    	                              value={q.max_score ?? ''}
    	                              onChange={(e) => {
    	                                const raw = e.target.value
    	                                const nextVal = raw === '' ? null : Number(raw)
    	                                updateExamQuestionField(idx, { max_score: nextVal })
    	                              }}
    	                            />
    	                          </div>
    	                        ))}
    	                      </div>
    	                    </div>
    	                    <div className="draft-card">
    	                      <h4>标准答案（可编辑）</h4>
    	                      <div className="draft-form">
    	                        <label>答案文本（每行一个，示例：1 A）</label>
    	                        <textarea
    	                          value={String(examDraft.answer_key_text || '')}
    	                          onChange={(e) => updateExamAnswerKeyText(e.target.value)}
    	                          onKeyDown={stopKeyPropagation}
    	                          rows={8}
    	                          placeholder={`示例：\n1 A\n2 C\n12(1) B`}
    	                        />
    	                      </div>
    	                      {examDraft.answer_text_excerpt ? (
    	                        <details style={{ marginTop: 8 }}>
    	                          <summary className="muted">查看识别到的答案文本（可用作填充参考）</summary>
    	                          <pre className="status ok" style={{ whiteSpace: 'pre-wrap' }}>
    	                            {String(examDraft.answer_text_excerpt)}
    	                          </pre>
    	                          <div className="draft-actions" style={{ marginTop: 8 }}>
    	                            <button
    	                              type="button"
    	                              className="secondary-btn"
    	                              onClick={() => {
    	                                if (!examDraft.answer_text_excerpt) return
    	                                updateExamAnswerKeyText(String(examDraft.answer_text_excerpt))
    	                              }}
    	                              disabled={!examDraft.answer_text_excerpt}
    	                            >
    	                              用识别文本填充
    	                            </button>
    	                          </div>
    	                        </details>
    	                      ) : (
    	                        <div className="muted">未检测到答案文件识别文本。你也可以直接粘贴答案文本。</div>
    	                      )}
    	                      <div className="muted" style={{ marginTop: 8 }}>
    	                        提示：保存草稿后，创建考试时会使用该答案对“作答字母但无分数”的客观题自动评分。
    	                      </div>
    	                    </div>
    	                  </div>
    	                </>
    	              )}
    	            </section>
    	          )}
    
              {uploadMode === 'assignment' && draftLoading && (
                <section className="draft-panel">
                  <h3>解析结果（审核/修改）</h3>
                  <div className="status ok">草稿加载中…</div>
                </section>
              )}
    
              {uploadMode === 'assignment' && draftError && (
                <section className="draft-panel">
                  <h3>解析结果（审核/修改）</h3>
                  <div className="status err">{draftError}</div>
                </section>
              )}
    
              {uploadMode === 'assignment' && uploadDraft && (
                <section id="workflow-assignment-draft-section" className={`draft-panel ${draftPanelCollapsed ? 'collapsed' : ''}`}>
                  <div className="panel-header">
                    <h3>解析结果（审核/修改）</h3>
                    {draftPanelCollapsed ? (
                      <div className="panel-summary" title={formatDraftSummary(uploadDraft, uploadJobInfo)}>
                        {formatDraftSummary(uploadDraft, uploadJobInfo)}
                      </div>
                    ) : null}
	                    <button type="button" className="ghost" onClick={() => setDraftPanelCollapsed((v: boolean) => !v)}>
                      {draftPanelCollapsed ? '展开' : '收起'}
                    </button>
                  </div>
                  {draftPanelCollapsed ? (
                    <></>
                  ) : (
                    <>
                      <div className="draft-meta">
                        <div>作业编号：{uploadDraft.assignment_id}</div>
                        <div>日期：{uploadDraft.date}</div>
                        <div>
                          范围：
                          {uploadDraft.scope === 'public'
                            ? '公共作业'
                            : uploadDraft.scope === 'class'
                              ? '班级作业'
                              : '私人作业'}
                        </div>
                        {uploadDraft.class_name ? <div>班级：{uploadDraft.class_name}</div> : null}
                        {uploadDraft.student_ids && uploadDraft.student_ids.length ? (
                          <div>学生：{uploadDraft.student_ids.join('、')}</div>
                        ) : null}
                        <div>题目数量：{uploadDraft.questions?.length || 0}</div>
                        <div>交付方式：{uploadDraft.delivery_mode === 'pdf' ? '文档' : '图片'}</div>
                        {uploadDraft.requirements_missing && uploadDraft.requirements_missing.length ? (
                          <div className="missing">
                            缺失项：{formatMissingRequirements(uploadDraft.requirements_missing)}（补全后才能创建）
                          </div>
                        ) : (
                          <div className="ok">作业要求已补全，可创建。</div>
                        )}
                      </div>
    
                      {draftActionError && <div className="status err">{draftActionError}</div>}
                      {draftActionStatus && <pre className="status ok">{draftActionStatus}</pre>}
    
                      <div className="draft-actions">
                        <button
                          type="button"
                          className="secondary-btn"
                          onClick={() => {
                            if (!uploadDraft) return
                            void saveDraft(uploadDraft).catch(() => {})
                          }}
                          disabled={draftSaving}
                        >
                          {draftSaving ? '保存中…' : '保存草稿'}
                        </button>
                        <button
                          type="button"
                          className="confirm-btn"
                          onClick={handleConfirmUpload}
                          disabled={
                            uploadConfirming ||
                            (uploadJobInfo ? uploadJobInfo.status !== 'done' : false) ||
                            ((uploadDraft.requirements_missing?.length || 0) > 0)
                          }
                          title={
                            uploadJobInfo && uploadJobInfo.status !== 'done'
                              ? uploadJobInfo.status === 'confirmed' || uploadJobInfo.status === 'created'
                                ? '作业已创建，无需重复创建'
                                : '解析未完成，暂不可创建'
                              : uploadDraft.requirements_missing && uploadDraft.requirements_missing.length
                                ? `请先补全：${formatMissingRequirements(uploadDraft.requirements_missing)}`
                                : ''
                          }
                        >
                          {uploadConfirming
                            ? uploadJobInfo && (uploadJobInfo.status as any) === 'confirming'
                              ? `创建中…${uploadJobInfo.progress ?? 0}%`
                              : '创建中…'
                            : uploadJobInfo && (uploadJobInfo.status === 'confirmed' || uploadJobInfo.status === 'created')
                              ? '已创建'
                              : '创建作业'}
                        </button>
                      </div>
    
                      <div className="draft-grid">
                    <div className="draft-card">
                      <h4>作业 8 点要求（可编辑）</h4>
                      <div className="draft-form">
                        <label>1) 学科</label>
                        <input value={uploadDraft.requirements?.subject || ''} onChange={(e) => updateDraftRequirement('subject', e.target.value)} />
                        <label>1) 本节课主题</label>
                        <input value={uploadDraft.requirements?.topic || ''} onChange={(e) => updateDraftRequirement('topic', e.target.value)} />
                        <label>2) 年级</label>
                        <input value={uploadDraft.requirements?.grade_level || ''} onChange={(e) => updateDraftRequirement('grade_level', e.target.value)} />
                        <label>2) 班级水平（偏弱/中等/较强/混合）</label>
                        <select
                          value={uploadDraft.requirements?.class_level || ''}
                          onChange={(e) => updateDraftRequirement('class_level', e.target.value)}
                          onKeyDown={stopKeyPropagation}
                        >
                          <option value="">未设置</option>
                          <option value="偏弱">偏弱</option>
                          <option value="中等">中等</option>
                          <option value="较强">较强</option>
                          <option value="混合">混合</option>
                        </select>
                        <label>3) 核心概念（逗号分隔 3–8 个）</label>
                        <input
                          value={(uploadDraft.requirements?.core_concepts || []).join('，')}
                          onChange={(e) => updateDraftRequirement('core_concepts', parseCommaList(e.target.value))}
                        />
                        <label>4) 典型题型/例题特征</label>
                        <textarea
                          value={uploadDraft.requirements?.typical_problem || ''}
                          onChange={(e) => updateDraftRequirement('typical_problem', e.target.value)}
                          onKeyDown={stopKeyPropagation}
                          rows={3}
                        />
                        <label>5) 易错点（每行一条，至少 4 条）</label>
                        <textarea
                          value={misconceptionsText}
                          onChange={(e) => {
                            setMisconceptionsText(e.target.value)
                            setMisconceptionsDirty(true)
                            // Also keep structured requirements up to date for any immediate UI reads.
                            updateDraftRequirement('misconceptions', parseLineList(e.target.value))
                          }}
                          onKeyDown={stopKeyPropagation}
                          placeholder={'示例：\n1) 调零本质理解错误\n2) 换挡不重新调零\n3) 读数方向/单位混淆\n4) 内阻影响忽略'}
                          rows={4}
                        />
                        <label>6) 作业时间（20/40/60）</label>
                        <select
                          value={String(uploadDraft.requirements?.duration_minutes || '')}
                          onChange={(e) => updateDraftRequirement('duration_minutes', Number(e.target.value))}
                        >
                          <option value="">未设置</option>
                          <option value="20">20</option>
                          <option value="40">40</option>
                          <option value="60">60</option>
                        </select>
                        <label>7) 作业偏好（逗号分隔）</label>
                        <input
                          value={(uploadDraft.requirements?.preferences || []).join('，')}
                          onChange={(e) => updateDraftRequirement('preferences', parseCommaList(e.target.value))}
                          placeholder="例如：B提升，E小测验"
                        />
                        <label>8) 额外限制</label>
                        <textarea
                          value={uploadDraft.requirements?.extra_constraints || ''}
                          onChange={(e) => updateDraftRequirement('extra_constraints', e.target.value)}
                          onKeyDown={stopKeyPropagation}
                          rows={2}
                        />
                      </div>
                    </div>
    
                    <div className="draft-card">
                      <h4>题目与答案（可编辑）</h4>
                      <div className="draft-hint">题目较多时可先修改关键题，点击“保存草稿”后再创建。</div>
	                      {(uploadDraft.questions || []).slice(0, questionShowCount).map((q: any, idx: number) => (
                        <details key={idx} className="question-item" open={idx < 1}>
                          <summary>
                            Q{idx + 1} · {(q.kp || q.kp_id || '未分类') as any} · {difficultyLabel(q.difficulty)}
                          </summary>
                          <div className="question-fields">
                            <label>题干</label>
                            <textarea
                              value={q.stem || ''}
                              onChange={(e) => updateDraftQuestion(idx, { stem: e.target.value })}
                              onKeyDown={stopKeyPropagation}
                              rows={4}
                            />
                            <label>答案</label>
                            <textarea
                              value={q.answer || ''}
                              onChange={(e) => updateDraftQuestion(idx, { answer: e.target.value })}
                              onKeyDown={stopKeyPropagation}
                              rows={3}
                            />
                            <div className="row2">
                              <div>
                                <label>分值</label>
                                <input
                                  value={q.score ?? ''}
                                  onChange={(e) => updateDraftQuestion(idx, { score: Number(e.target.value) || 0 })}
                                  placeholder="0"
                                />
                              </div>
                              <div>
                                <label>难度</label>
                                <select
                                  value={normalizeDifficulty(q.difficulty)}
                                  onChange={(e) => updateDraftQuestion(idx, { difficulty: e.target.value })}
                                >
                                  {difficultyOptions.map((opt) => (
                                    <option key={opt.value} value={opt.value}>
                                      {opt.label}
                                    </option>
                                  ))}
                                </select>
                              </div>
                            </div>
                            <div className="row2">
                              <div>
                                <label>知识点（kp）</label>
                                <input value={q.kp || ''} onChange={(e) => updateDraftQuestion(idx, { kp: e.target.value })} />
                              </div>
                              <div>
                                <label>标签（逗号分隔）</label>
                                <input
                                  value={Array.isArray(q.tags) ? q.tags.join('，') : q.tags || ''}
                                  onChange={(e) => updateDraftQuestion(idx, { tags: parseCommaList(e.target.value) })}
                                />
                              </div>
                            </div>
                            <label>题型（可选）</label>
                            <input value={q.type || ''} onChange={(e) => updateDraftQuestion(idx, { type: e.target.value })} />
                          </div>
                        </details>
                      ))}
                      {uploadDraft.questions && uploadDraft.questions.length > questionShowCount && (
                        <div className="draft-actions">
	                          <button type="button" className="secondary-btn" onClick={() => setQuestionShowCount((n: number) => n + 20)}>
                            加载更多（+20）
                          </button>
                        </div>
                      )}
                    </div>
                      </div>
                    </>
                  )}
                </section>
              )}
    
    
                  </section>
                ) : (
                  <section className="memory-panel workbench-memory">
                    <div className="history-header">
                      <strong>自动记忆记录</strong>
                      <div className="history-actions">
                        <div className="view-switch">
                          <button
                            type="button"
                            className={memoryStatusFilter === 'applied' ? 'active' : ''}
                            onClick={() => setMemoryStatusFilter('applied')}
                          >
                            已写入
                          </button>
                          <button
                            type="button"
                            className={memoryStatusFilter === 'rejected' ? 'active' : ''}
                            onClick={() => setMemoryStatusFilter('rejected')}
                          >
                            已拦截
                          </button>
                          <button
                            type="button"
                            className={memoryStatusFilter === 'all' ? 'active' : ''}
                            onClick={() => setMemoryStatusFilter('all')}
                          >
                            全部
                          </button>
                        </div>
                      </div>
                    </div>
                    {memoryInsights?.summary && (
                      <div className="memory-metrics-grid">
                        <div className="memory-metric-card">
                          <div className="memory-metric-value">{memoryInsights.summary.active_total ?? 0}</div>
                          <div className="memory-metric-label">活跃记忆</div>
                        </div>
                        <div className="memory-metric-card">
                          <div className="memory-metric-value">{memoryInsights.summary.expired_total ?? 0}</div>
                          <div className="memory-metric-label">已过期</div>
                        </div>
                        <div className="memory-metric-card">
                          <div className="memory-metric-value">{memoryInsights.summary.superseded_total ?? 0}</div>
                          <div className="memory-metric-label">已替代</div>
                        </div>
                        <div className="memory-metric-card">
                          <div className="memory-metric-value">{memoryInsights.summary.avg_priority_active ?? 0}</div>
                          <div className="memory-metric-label">平均优先级</div>
                        </div>
                        <div className="memory-metric-card">
                          <div className="memory-metric-value">
                            {`${Math.round((memoryInsights.retrieval?.search_hit_rate ?? 0) * 100)}%`}
                          </div>
                          <div className="memory-metric-label">检索命中率(14d)</div>
                        </div>
                        <div className="memory-metric-card">
                          <div className="memory-metric-value">{memoryInsights.retrieval?.search_calls ?? 0}</div>
                          <div className="memory-metric-label">检索次数(14d)</div>
                        </div>
                      </div>
                    )}
                    {Array.isArray(memoryInsights?.top_queries) && (memoryInsights?.top_queries || []).length > 0 && (
                      <div className="memory-query-list">
                        <div className="muted">高频命中查询（14天）</div>
	                        {(memoryInsights?.top_queries || []).slice(0, 5).map((q: any) => (
                          <div key={q.query} className="proposal-meta">
                            <span>{q.query}</span>
                            <span>
                              {q.hit_calls}/{q.calls}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                    {proposalError ? <div className="status err">{proposalError}</div> : null}
                    {!proposalLoading && proposals.length === 0 ? <div className="history-hint">暂无记录。</div> : null}
                    {proposals.length > 0 && (
                      <div className="proposal-list">
                        {proposals.map((p) => (
                          <div key={p.proposal_id} className="proposal-item">
                            <div className="proposal-title">
                              {p.title || 'Memory Update'} <span className="muted">[{p.target || 'MEMORY'}]</span>
                            </div>
                            <div className="proposal-meta">
                              <span>{p.created_at || '-'}</span>
                              <span>{p.source || 'manual'}</span>
                              <span className={`memory-status-chip ${String(p.status || '').toLowerCase() || 'unknown'}`}>
                                {String(p.status || '').toLowerCase() === 'applied'
                                  ? '已写入'
                                  : String(p.status || '').toLowerCase() === 'rejected'
                                    ? '已拦截'
                                    : '待处理'}
                              </span>
                            </div>
                            <div className="proposal-content">{p.content || ''}</div>
                            <div className="proposal-meta">
                              <span>{p.proposal_id}</span>
                              <span>{p.applied_at || p.rejected_at || '-'}</span>
                            </div>
                            {p.reject_reason ? <div className="muted">原因：{p.reject_reason}</div> : null}
                          </div>
                        ))}
                      </div>
                    )}
                  </section>
                )}
              </aside>
  )
}
