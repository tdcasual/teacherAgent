type AssignmentProgressSectionProps = {
  progressPanelCollapsed: boolean
  setProgressPanelCollapsed: any
  formatProgressSummary: any
  progressData: any
  progressAssignmentId: any
  setProgressAssignmentId: any
  progressOnlyIncomplete: boolean
  setProgressOnlyIncomplete: any
  progressLoading: boolean
  fetchAssignmentProgress: any
  progressError: any
}

export default function AssignmentProgressSection(props: AssignmentProgressSectionProps) {
  const {
    progressPanelCollapsed, setProgressPanelCollapsed, formatProgressSummary,
    progressData, progressAssignmentId, setProgressAssignmentId,
    progressOnlyIncomplete, setProgressOnlyIncomplete,
    progressLoading, fetchAssignmentProgress, progressError,
  } = props

  return (
    	            <section id="workflow-progress-section" className={`mt-3 bg-surface border border-border rounded-[14px] shadow-sm ${progressPanelCollapsed ? 'py-[10px] px-3' : 'p-[10px]'}`}>
    	              <div className={`flex items-start gap-2 flex-wrap ${progressPanelCollapsed ? 'mb-0' : 'mb-2'}`}>
    	                <h3 className="m-0 whitespace-nowrap shrink-0">作业完成情况</h3>
    	                {progressPanelCollapsed ? (
    	                  <div
    	                    className="flex-1 min-w-0 text-muted text-[12px] whitespace-nowrap overflow-hidden text-ellipsis"
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
    	                  <div className="flex items-end justify-between gap-3 flex-wrap mb-[10px]">
    	                    <div className="grid gap-1.5 min-w-[240px]">
    	                      <label>作业编号</label>
    	                      <input
    	                        value={progressAssignmentId}
    	                        onChange={(e) => setProgressAssignmentId(e.target.value)}
    	                        placeholder="例如：A2403_2026-02-04"
    	                      />
    	                    </div>
    	                    <div className="flex items-center gap-3 flex-wrap">
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
    	                        className="border border-border rounded-xl py-[10px] px-[14px] bg-white text-ink cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
    	                        disabled={progressLoading}
    	                        onClick={() => void fetchAssignmentProgress()}
    	                      >
    	                        {progressLoading ? '加载中…' : '刷新'}
    	                      </button>
    	                    </div>
    	                  </div>

    	                  {progressError && <div className="mt-[10px] p-[10px_12px] rounded-xl text-[12px] whitespace-pre-wrap overflow-x-auto bg-danger-soft text-danger">{progressError}</div>}
    	                  {progressData && (
    	                    <div className="text-[13px] text-muted grid gap-1">
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
    	                    <div className="mt-3 grid gap-2">
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
    	                          <div key={s.student_id} className={`progress-row border rounded-[14px] py-[10px] px-3 bg-white flex justify-between gap-3 items-start ${s.complete ? 'border-[#b8d8d6] bg-[#f3fbfa]' : 'border-[#e2b6b6] bg-[#fff8f8]'}`}>
    	                            <div className="text-[13px]">
    	                              <strong>{s.student_id}</strong>
    	                              {name ? <span className="text-muted text-[12px]"> {name}</span> : null}
    	                            </div>
    	                            <div className="text-[12px] text-muted whitespace-nowrap">
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
  )
}
