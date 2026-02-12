import type { AssignmentDraftSectionProps, AssignmentQuestion } from '../../../types/workflow'

type Props = AssignmentDraftSectionProps & {
  draftSaving: boolean
  uploadConfirming: boolean
}

export default function AssignmentDraftSection(props: Props) {
  const {
    uploadDraft, uploadJobInfo,
    draftPanelCollapsed, setDraftPanelCollapsed,
    draftActionError, draftActionStatus,
    draftSaving, saveDraft, handleConfirmUpload, uploadConfirming,
    formatDraftSummary, formatMissingRequirements,
    updateDraftRequirement, updateDraftQuestion,
    misconceptionsText, setMisconceptionsText, setMisconceptionsDirty,
    parseCommaList, parseLineList,
    difficultyLabel, difficultyOptions, normalizeDifficulty,
    questionShowCount, setQuestionShowCount,
    stopKeyPropagation,
  } = props

  return (
                <section id="workflow-assignment-draft-section" className={`mt-3 bg-surface border border-border rounded-[14px] shadow-sm ${draftPanelCollapsed ? 'py-[10px] px-3' : 'p-[10px]'}`}>
                  <div className={`flex items-start gap-2 flex-wrap ${draftPanelCollapsed ? 'mb-0' : 'mb-2'}`}>
                    <h3 className="m-0 whitespace-nowrap shrink-0">解析结果（审核/修改）</h3>
                    {draftPanelCollapsed ? (
                      <div className="flex-1 min-w-0 text-muted text-[12px] whitespace-nowrap overflow-hidden text-ellipsis" title={formatDraftSummary(uploadDraft, uploadJobInfo)}>
                        {formatDraftSummary(uploadDraft, uploadJobInfo)}
                      </div>
                    ) : null}
	                    <button type="button" className="ghost" onClick={() => setDraftPanelCollapsed((v: boolean) => !v)}>
                      {draftPanelCollapsed ? '展开' : '收起'}
                    </button>
                  </div>
                  {draftPanelCollapsed || !uploadDraft ? (
                    <></>
                  ) : (
                    <>
                      <div className="text-[13px] text-muted grid gap-1">
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
                          <div className="text-[#8a1f1f] font-semibold">
                            缺失项：{formatMissingRequirements(uploadDraft.requirements_missing)}（补全后才能创建）
                          </div>
                        ) : (
                          <div className="text-[#2f6d6b] font-semibold">作业要求已补全，可创建。</div>
                        )}
                      </div>

                      {draftActionError && <div className="mt-[10px] p-[10px_12px] rounded-xl text-[12px] whitespace-pre-wrap overflow-x-auto bg-danger-soft text-danger">{draftActionError}</div>}
                      {draftActionStatus && <pre className="mt-[10px] p-[10px_12px] rounded-xl text-[12px] whitespace-pre-wrap overflow-x-auto bg-[#e8f7f2] text-[#0f766e]">{draftActionStatus}</pre>}

                      <div className="mt-[10px] flex gap-[10px] justify-end flex-wrap">
                        <button
                          type="button"
                          className="border border-border rounded-xl py-[10px] px-[14px] bg-white text-ink cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
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
                          className="confirm-btn border-none rounded-xl py-[10px] px-[14px] bg-[#2f6d6b] text-white cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
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
                            ? uploadJobInfo && uploadJobInfo.status === 'confirming'
                              ? `创建中…${uploadJobInfo.progress ?? 0}%`
                              : '创建中…'
                            : uploadJobInfo && (uploadJobInfo.status === 'confirmed' || uploadJobInfo.status === 'created')
                              ? '已创建'
                              : '创建作业'}
                        </button>
                      </div>

                      <div className="mt-3 grid gap-3 grid-cols-1">
                    <div className="draft-card border border-border rounded-[16px] p-3 bg-white">
                      <h4 className="m-0 mb-[10px]">作业 8 点要求（可编辑）</h4>
                      <div className="grid gap-2">
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

                    <div className="draft-card border border-border rounded-[16px] p-3 bg-white">
                      <h4 className="m-0 mb-[10px]">题目与答案（可编辑）</h4>
                      <div className="text-muted text-[12px] mb-[10px]">题目较多时可先修改关键题，点击"保存草稿"后再创建。</div>
	                      {(uploadDraft.questions || []).slice(0, questionShowCount).map((q: AssignmentQuestion, idx: number) => (
                        <details key={idx} className="border border-border rounded-[14px] py-2 px-[10px] mb-[10px] bg-[#fbfaf7]" open={idx < 1}>
                          <summary>
                            Q{idx + 1} · {(q.kp || q.kp_id || '未分类')} · {difficultyLabel(q.difficulty)}
                          </summary>
                          <div className="mt-[10px] grid gap-2">
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
                            <div className="grid gap-[10px] grid-cols-1">
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
                            <div className="grid gap-[10px] grid-cols-1">
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
                        <div className="mt-[10px] flex gap-[10px] justify-end flex-wrap">
	                          <button type="button" className="border border-border rounded-xl py-[10px] px-[14px] bg-white text-ink cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed" onClick={() => setQuestionShowCount((n: number) => n + 20)}>
                            加载更多（+20）
                          </button>
                        </div>
                      )}
                    </div>
                      </div>
                    </>
                  )}
                </section>
  )
}
