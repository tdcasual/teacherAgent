import { useState } from 'react'
import type {
  ExamConflictLevel,
  CandidateSummarySort,
  ParsedCandidateSummary,
  RecommendedCandidate,
  ConflictStudent,
} from './examCandidateAnalysis'
import {
  getExamConflictThreshold,
  getExamConflictLevelLabel,
  sortCandidateSummaries,
  computeRecommendedCandidate,
  computeConflictStudents,
} from './examCandidateAnalysis'

type ExamDraftSectionProps = {
  examDraft: any
  examDraftLoading: boolean
  examDraftError: any
  examDraftPanelCollapsed: boolean
  setExamDraftPanelCollapsed: any
  examDraftSaving: boolean
  examDraftActionError: any
  examDraftActionStatus: any
  examConfirming: boolean
  examJobInfo: any
  formatExamDraftSummary: any
  saveExamDraft: any
  handleConfirmExamUpload: any
  updateExamDraftMeta: any
  updateExamQuestionField: any
  updateExamAnswerKeyText: any
  updateExamScoreSchemaSelectedCandidate: any
  stopKeyPropagation: any
}

export default function ExamDraftSection(props: ExamDraftSectionProps) {
  const {
    examDraft, examDraftLoading, examDraftError,
    examDraftPanelCollapsed, setExamDraftPanelCollapsed,
    examDraftSaving, examDraftActionError, examDraftActionStatus,
    examConfirming, examJobInfo, formatExamDraftSummary,
    saveExamDraft, handleConfirmExamUpload,
    updateExamDraftMeta, updateExamQuestionField,
    updateExamAnswerKeyText, updateExamScoreSchemaSelectedCandidate,
    stopKeyPropagation,
  } = props

  const [examConflictLevel, setExamConflictLevel] = useState<ExamConflictLevel>('standard')
  const [candidateSummarySort, setCandidateSummarySort] = useState<CandidateSummarySort>('quality')
  const [candidateSummaryTopOnly, setCandidateSummaryTopOnly] = useState(false)

  if (examDraftLoading) {
    return (
      <section className="mt-3 bg-surface border border-border rounded-[14px] p-[10px] shadow-sm">
        <h3>考试解析结果（审核/修改）</h3>
        <div className="mt-[10px] p-[10px_12px] rounded-xl text-[12px] whitespace-pre-wrap bg-[#e8f7f2] text-[#0f766e]">草稿加载中…</div>
      </section>
    )
  }

  if (examDraftError) {
    return (
      <section className="mt-3 bg-surface border border-border rounded-[14px] p-[10px] shadow-sm">
        <h3>考试解析结果（审核/修改）</h3>
        <div className="mt-[10px] p-[10px_12px] rounded-xl text-[12px] whitespace-pre-wrap bg-danger-soft text-danger">{examDraftError}</div>
      </section>
    )
  }

  if (!examDraft) return null

  const examNeedsConfirm = Boolean(examDraft?.needs_confirm || examDraft?.score_schema?.needs_confirm)
  const examSubjectSchema = examDraft?.score_schema?.subject || {}
  const examCandidateColumns = Array.isArray(examSubjectSchema?.candidate_columns) ? examSubjectSchema.candidate_columns : []
  const examCandidateSummaries = Array.isArray(examSubjectSchema?.candidate_summaries) ? examSubjectSchema.candidate_summaries : []
  const examSelectedCandidateId = String(examSubjectSchema?.selected_candidate_id || '')
  const examSuggestedCandidateId = String(examSubjectSchema?.suggested_selected_candidate_id || '')
  const examRecommendedCandidateId = String(examSubjectSchema?.recommended_candidate_id || '')
  const examRecommendedCandidateReason = String(examSubjectSchema?.recommended_candidate_reason || '')
  const examRequestedCandidateId = String(examSubjectSchema?.requested_candidate_id || '')
  const examSelectedCandidateAvailable = examSubjectSchema?.selected_candidate_available !== false
  const examSelectionError = String(examSubjectSchema?.selection_error || '')
  const examEffectiveCandidateId = examSelectedCandidateId || examSuggestedCandidateId || examRecommendedCandidateId
  const showExamCandidateCard = Boolean(examNeedsConfirm || examCandidateColumns.length)

  const examConflictThreshold = getExamConflictThreshold(examConflictLevel)
  const examConflictLevelLabel = getExamConflictLevelLabel(examConflictLevel)
  const examSortedCandidateSummaries = sortCandidateSummaries(examCandidateSummaries, candidateSummarySort, candidateSummaryTopOnly)
  const examRecommendedCandidate = computeRecommendedCandidate(examCandidateColumns, examRecommendedCandidateId)
  const examConflictStudents = computeConflictStudents(examCandidateColumns, examConflictThreshold)

  return (
    <section id="workflow-exam-draft-section" className={`mt-3 bg-surface border border-border rounded-[14px] shadow-sm ${examDraftPanelCollapsed ? 'py-[10px] px-3' : 'p-[10px]'}`}>
      <div className={`flex items-start gap-2 flex-wrap ${examDraftPanelCollapsed ? 'mb-0' : 'mb-2'}`}>
        <h3 className="m-0 whitespace-nowrap shrink-0">考试解析结果（审核/修改）</h3>
        {examDraftPanelCollapsed ? (
          <div className="flex-1 min-w-0 text-muted text-[12px] whitespace-nowrap overflow-hidden text-ellipsis" title={formatExamDraftSummary(examDraft, examJobInfo)}>
            {formatExamDraftSummary(examDraft, examJobInfo)}
          </div>
        ) : null}
        <button type="button" className="ghost" onClick={() => setExamDraftPanelCollapsed((v: boolean) => !v)}>
          {examDraftPanelCollapsed ? '展开' : '收起'}
        </button>
      </div>
      {examDraftPanelCollapsed ? null : (
        <>
          <div className="text-[13px] text-muted grid gap-1">
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
              <div className="text-muted text-[12px]">
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

          {examDraftActionError && <div className="mt-[10px] p-[10px_12px] rounded-xl text-[12px] whitespace-pre-wrap overflow-x-auto bg-danger-soft text-danger">{examDraftActionError}</div>}
          {examDraftActionStatus && <pre className="mt-[10px] p-[10px_12px] rounded-xl text-[12px] whitespace-pre-wrap overflow-x-auto bg-[#e8f7f2] text-[#0f766e]">{examDraftActionStatus}</pre>}

          {examNeedsConfirm ? (
            <div className="mt-[10px] p-[10px_12px] rounded-xl text-[12px] whitespace-pre-wrap overflow-x-auto bg-danger-soft text-danger">
              当前成绩映射置信度不足，请先在\u201c物理分映射确认\u201d里选择映射列并保存草稿，等待重新解析完成后再创建考试。
            </div>
          ) : null}

          <div className="mt-[10px] flex gap-[10px] justify-end flex-wrap">
            <button
              type="button"
              className="border border-border rounded-xl py-[10px] px-[14px] bg-white text-ink cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
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

          <div className="mt-3 grid gap-3 grid-cols-1">
            {showExamCandidateCard ? (
              <div className="border border-border rounded-[16px] p-3 bg-white">
                <h4 className="m-0 mb-[10px]">物理分映射确认</h4>
                <div className="grid gap-2">
                  <label>映射候选列</label>
                  {examCandidateColumns.length ? (
                    <>
                      <select
                        value={examEffectiveCandidateId}
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
                        <div className="mt-2 flex gap-[10px] justify-end flex-wrap">
                          <button
                            type="button"
                            className="border border-border rounded-xl py-[10px] px-[14px] bg-white text-ink cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
                            onClick={() => updateExamScoreSchemaSelectedCandidate(examRecommendedCandidate.candidateId)}
                            disabled={examEffectiveCandidateId === examRecommendedCandidate.candidateId}
                          >
                            {examEffectiveCandidateId === examRecommendedCandidate.candidateId
                              ? '已使用推荐映射'
                              : '一键使用推荐映射'}
                          </button>
                        </div>
                      ) : null}
                    </>
                  ) : (
                    <div className="mt-[10px] p-[10px_12px] rounded-xl text-[12px] whitespace-pre-wrap overflow-x-auto bg-danger-soft text-danger">未检测到可确认的物理分映射列。建议更换更规范的成绩表后重试。</div>
                  )}
                </div>
                {examRecommendedCandidate ? (
                  <div className="mt-[10px] p-[10px_12px] rounded-xl text-[12px] whitespace-pre-wrap overflow-x-auto bg-[#e8f7f2] text-[#0f766e]">
                    推荐映射：{examRecommendedCandidate.candidateId}（命中 {examRecommendedCandidate.rowsParsed}/
                    {examRecommendedCandidate.rowsConsidered}，无效 {examRecommendedCandidate.rowsInvalid}）
                  </div>
                ) : null}
                {examRecommendedCandidateId ? (
                  <div className="text-muted text-[12px]" style={{ marginTop: 4 }}>
                    系统推荐：{examRecommendedCandidateId}
                    {examRecommendedCandidateReason ? `（${examRecommendedCandidateReason}）` : ''}
                    {!examSelectedCandidateId && examSuggestedCandidateId
                      ? '；当前为建议选中，保存后将按该映射重跑。'
                      : ''}
                  </div>
                ) : null}
                {examCandidateSummaries.length ? (
                  <details style={{ marginTop: 8 }}>
                    <summary className="text-muted text-[12px]">查看候选映射评分详情</summary>
                    <div className="grid gap-2 mt-2">
                      <label>排序方式</label>
                      <select
                        value={candidateSummarySort}
                        onChange={(e) => {
                          const raw = String(e.target.value || '')
                          const next: CandidateSummarySort =
                            raw === 'parsed_rate' || raw === 'source_rank' ? raw : 'quality'
                          setCandidateSummarySort(next)
                        }}
                        onKeyDown={stopKeyPropagation}
                      >
                        <option value="quality">按评分</option>
                        <option value="parsed_rate">按解析率</option>
                        <option value="source_rank">按来源等级</option>
                      </select>
                      <label className="toggle inline-flex items-center gap-1.5">
                        <input
                          type="checkbox"
                          checked={candidateSummaryTopOnly}
                          onChange={(e) => setCandidateSummaryTopOnly(e.target.checked)}
                          onKeyDown={stopKeyPropagation}
                        />
                        只看 Top 3
                      </label>
                    </div>
                    <div className="mt-2 grid gap-2">
                      {examSortedCandidateSummaries.map((item: any, idx: number) => {
                        const cid = String(item?.candidateId || '')
                        if (!cid) return null
                        const parsed = Number(item?.rowsParsed || 0)
                        const considered = Number(item?.rowsConsidered || 0)
                        const invalid = Number(item?.rowsInvalid || 0)
                        const rate = Number(item?.parsedRate || 0)
                        const sourceRank = Number(item?.sourceRank || 99)
                        const quality = Number(item?.qualityScore || 0)
                        const fileLabel = Array.isArray(item?.files) ? item.files.filter(Boolean).join('、') : ''
                        const typeLabel = Array.isArray(item?.types) ? item.types.filter(Boolean).join('、') : ''
                        return (
                          <div
                            key={`${cid}-${idx}`}
                            className={`border rounded-[10px] py-2 px-[10px] flex gap-2 flex-wrap items-center ${
                              cid === examRecommendedCandidateId
                                ? 'border-[#8bd7c7] bg-[#f0fbf7]'
                                : 'border-border bg-[#fbfaf7]'
                            }`}
                          >
                            <strong>{cid}</strong>
                            <span className={cid === examRecommendedCandidateId ? 'inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold leading-[1.4] bg-[#e8f7f2] text-[#0f766e]' : 'inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold leading-[1.4]'}>
                              {cid === examRecommendedCandidateId ? '推荐' : '候选'}
                            </span>
                            <span className="text-muted text-[12px]">
                              命中 {parsed}/{considered}；无效 {invalid}；解析率 {(rate * 100).toFixed(1)}%；来源等级 {sourceRank}；评分 {quality.toFixed(1)}
                            </span>
                            {fileLabel ? <span className="text-muted text-[12px]">文件：{fileLabel}</span> : null}
                            {typeLabel ? <span className="text-muted text-[12px]">类型：{typeLabel}</span> : null}
                          </div>
                        )
                      })}
                    </div>
                  </details>
                ) : null}
                {examCandidateColumns.length > 1 ? (
                  <div className="grid gap-2" style={{ marginTop: 8 }}>
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
                    <div className="text-muted text-[12px]">当前模式：{examConflictLevelLabel}（阈值 {examConflictThreshold} 分）</div>
                  </div>
                ) : null}
                {examConflictStudents.length ? (
                  <details style={{ marginTop: 8 }}>
                    <summary className="text-muted text-[12px]">查看样本冲突学生（候选列分差较大）</summary>
                    <div className="mt-2 grid gap-2">
                      {examConflictStudents.map((item, idx) => {
                        const studentLabel = [item.studentName, item.studentId ? `(${item.studentId})` : '']
                          .filter(Boolean)
                          .join(' ')
                        const detailLabel = item.entries.map((entry) => `${entry.candidateId}=${entry.score}`).join('；')
                        return (
                          <div key={`conflict-${idx}-${item.studentId || item.studentName}`} className="border border-danger-soft rounded-[10px] py-2 px-[10px] flex gap-2 flex-wrap items-center bg-[#fff5f5]">
                            <strong>{studentLabel || `样本学生 ${idx + 1}`}</strong>
                            <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold leading-[1.4] bg-danger-soft text-danger">分差 {item.spread.toFixed(1)}</span>
                            <span className="text-muted text-[12px]">{detailLabel}</span>
                          </div>
                        )
                      })}
                    </div>
                  </details>
                ) : null}
                {(examRequestedCandidateId && !examSelectedCandidateAvailable) || examSelectionError === 'selected_candidate_not_found' ? (
                  <div className="mt-[10px] p-[10px_12px] rounded-xl text-[12px] whitespace-pre-wrap overflow-x-auto bg-danger-soft text-danger">
                    上次选择的映射列在当前文件中不可用，已回退自动匹配，请重新选择。
                    {examRecommendedCandidateId ? ` 推荐候选：${examRecommendedCandidateId}。` : ''}
                  </div>
                ) : null}
                {examSelectedCandidateId ? (
                  <div className="mt-[10px] p-[10px_12px] rounded-xl text-[12px] whitespace-pre-wrap overflow-x-auto bg-[#e8f7f2] text-[#0f766e]">当前已选映射：{examSelectedCandidateId}</div>
                ) : examSuggestedCandidateId ? (
                  <div className="mt-[10px] p-[10px_12px] rounded-xl text-[12px] whitespace-pre-wrap overflow-x-auto bg-[#e8f7f2] text-[#0f766e]">当前建议映射：{examSuggestedCandidateId}（未确认）</div>
                ) : null}
                <div className="text-muted text-[12px]" style={{ marginTop: 8 }}>
                  选择后点击\u201c保存草稿\u201d，系统会按所选映射重跑解析；重跑完成后可创建考试。
                </div>
                {Array.isArray(examSubjectSchema?.unresolved_students) && examSubjectSchema.unresolved_students.length ? (
                  <div className="text-muted text-[12px]" style={{ marginTop: 4 }}>
                    未解析到物理分学生：{examSubjectSchema.unresolved_students.length} 人（将按高置信结果保留）。
                  </div>
                ) : null}
                {examEffectiveCandidateId ? (
                  <details style={{ marginTop: 8 }}>
                    <summary className="text-muted text-[12px]">查看当前映射样本预览（最多 5 行）</summary>
                    {(() => {
                      const selected = examCandidateColumns.find(
                        (candidate: any) => String(candidate?.candidate_id || '') === examEffectiveCandidateId,
                      )
                      const rows = Array.isArray(selected?.sample_rows) ? selected.sample_rows : []
                      if (!rows.length) return <div className="text-muted text-[12px]">当前映射暂无样本行。</div>
                      return (
                        <div className="mt-2 grid gap-2">
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
                              <div key={`${examEffectiveCandidateId}-sample-${rowIdx}`} className="border border-border rounded-[10px] py-2 px-[10px] flex gap-2 flex-wrap items-center bg-[#fbfaf7]">
                                <strong>{label || `样本 ${rowIdx + 1}`}</strong>
                                <span className={row?.status === 'parsed' ? 'inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold leading-[1.4] bg-[#e8f7f2] text-[#0f766e]' : 'inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold leading-[1.4] bg-danger-soft text-danger'}>{statusLabel}</span>
                                <span className="text-muted text-[12px]">原始值：{String(row?.raw_value || '（空）')}{scoreLabel}</span>
                              </div>
                            )
                          })}
                        </div>
                      )
                    })()}
                  </details>
                ) : null}
                {(examSubjectSchema?.coverage !== undefined || examDraft?.score_schema?.confidence !== undefined) ? (
                  <div className="text-muted text-[12px]" style={{ marginTop: 4 }}>
                    当前覆盖率：{examSubjectSchema?.coverage ?? '-'}；置信度：{examDraft?.score_schema?.confidence ?? '-'}。
                  </div>
                ) : null}
              </div>
            ) : null}
            <div className="border border-border rounded-[16px] p-3 bg-white">
              <h4 className="m-0 mb-[10px]">考试信息（可编辑）</h4>
              <div className="grid gap-2">
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
            <div className="border border-border rounded-[16px] p-3 bg-white">
              <h4 className="m-0 mb-[10px]">题目满分（可编辑）</h4>
              <div className="grid gap-2">
                {(examDraft.questions || []).map((q: any, idx: number) => (
                  <div className="grid gap-[10px] grid-cols-[90px_minmax(0,1fr)_120px] items-center py-2 px-[10px] border border-border rounded-[14px] bg-[#fbfaf7]" key={`${q.question_id || 'q'}-${idx}`}>
                    <div className="font-mono font-bold text-ink">{q.question_id || `Q${idx + 1}`}</div>
                    <div className="text-muted text-[12px]">{q.question_no ? `题号 ${q.question_no}` : ''}</div>
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
            <div className="border border-border rounded-[16px] p-3 bg-white">
              <h4 className="m-0 mb-[10px]">标准答案（可编辑）</h4>
              <div className="grid gap-2">
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
                  <summary className="text-muted text-[12px]">查看识别到的答案文本（可用作填充参考）</summary>
                  <pre className="mt-[10px] p-[10px_12px] rounded-xl text-[12px] whitespace-pre-wrap overflow-x-auto bg-[#e8f7f2] text-[#0f766e]" style={{ whiteSpace: 'pre-wrap' }}>
                    {String(examDraft.answer_text_excerpt)}
                  </pre>
                  <div className="mt-2 flex gap-[10px] justify-end flex-wrap">
                    <button
                      type="button"
                      className="border border-border rounded-xl py-[10px] px-[14px] bg-white text-ink cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
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
                <div className="text-muted text-[12px]">未检测到答案文件识别文本。你也可以直接粘贴答案文本。</div>
              )}
              <div className="text-muted text-[12px]" style={{ marginTop: 8 }}>
                提示：保存草稿后，创建考试时会使用该答案对\u201c作答字母但无分数\u201d的客观题自动评分。
              </div>
            </div>
          </div>
        </>
      )}
    </section>
  )
}
