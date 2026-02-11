import { useState } from 'react'
import type { Skill } from '../../../appTypes'

export type SkillsTabProps = {
  apiBase: string
  filteredSkills: Skill[]
  favorites: string[]
  activeSkillId: string | null
  skillPinned: boolean
  skillQuery: string
  showFavoritesOnly: boolean
  skillsLoading: boolean
  skillsError: string
  fetchSkills: () => void | Promise<void>
  chooseSkill: (id: string, pin: boolean) => void
  toggleFavorite: (id: string) => void
  insertPrompt: (prompt: string) => void
  insertInvocationTokenAtCursor: (type: string, id: string) => void
  stopKeyPropagation: (e: React.KeyboardEvent) => void
  setSkillQuery: (q: string) => void
  setShowFavoritesOnly: (v: boolean) => void
  setSkillPinned: (v: boolean) => void
  setComposerWarning: (msg: string) => void
}

export default function SkillsTab(props: SkillsTabProps) {
  const {
    apiBase,
    filteredSkills,
    favorites,
    activeSkillId,
    skillPinned,
    skillQuery,
    showFavoritesOnly,
    skillsLoading,
    skillsError,
    fetchSkills,
    chooseSkill,
    toggleFavorite,
    insertPrompt,
    insertInvocationTokenAtCursor,
    setSkillQuery,
    setShowFavoritesOnly,
    setSkillPinned,
    setComposerWarning,
  } = props

  const [showCreateForm, setShowCreateForm] = useState(false)
  const [showImportDialog, setShowImportDialog] = useState(false)
  const [createTitle, setCreateTitle] = useState('')
  const [createDesc, setCreateDesc] = useState('')
  const [createKeywords, setCreateKeywords] = useState('')
  const [createExamples, setCreateExamples] = useState('')
  const [createSaving, setCreateSaving] = useState(false)
  const [createError, setCreateError] = useState('')
  const [importUrl, setImportUrl] = useState('')
  const [importPreview, setImportPreview] = useState<any>(null)
  const [importLoading, setImportLoading] = useState(false)
  const [importError, setImportError] = useState('')
  const [editingSkillId, setEditingSkillId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [editDesc, setEditDesc] = useState('')
  const [editKeywords, setEditKeywords] = useState('')
  const [editExamples, setEditExamples] = useState('')
  const [editSaving, setEditSaving] = useState(false)
  const [editError, setEditError] = useState('')

  const handleCreateSkill = async () => {
    if (!createTitle.trim() || !createDesc.trim()) { setCreateError('标题和描述为必填项'); return }
    setCreateSaving(true); setCreateError('')
    try {
      const res = await fetch(`${apiBase}/teacher/skills`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: createTitle.trim(), description: createDesc.trim(),
          keywords: createKeywords.split(/[,，]/).map(s => s.trim()).filter(Boolean),
          examples: createExamples.split('\n').map(s => s.trim()).filter(Boolean),
        }),
      })
      const data = await res.json()
      if (!data.ok) { setCreateError(data.error || '创建失败'); return }
      setShowCreateForm(false); setCreateTitle(''); setCreateDesc(''); setCreateKeywords(''); setCreateExamples('')
      void fetchSkills()
    } catch (e: any) { setCreateError(e.message || '网络错误') } finally { setCreateSaving(false) }
  }

  const handleImportPreview = async () => {
    if (!importUrl.trim()) return
    setImportLoading(true); setImportError(''); setImportPreview(null)
    try {
      const res = await fetch(`${apiBase}/teacher/skills/preview`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ github_url: importUrl.trim() }),
      })
      const data = await res.json()
      if (!data.ok) { setImportError(data.error || data.detail || '预览失败'); return }
      setImportPreview(data)
    } catch (e: any) { setImportError(e.message || '网络错误') } finally { setImportLoading(false) }
  }

  const handleImportConfirm = async () => {
    if (!importUrl.trim()) return
    setImportLoading(true); setImportError('')
    try {
      const res = await fetch(`${apiBase}/teacher/skills/import`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ github_url: importUrl.trim() }),
      })
      const data = await res.json()
      if (!data.ok) { setImportError(data.error || data.detail || '导入失败'); return }
      setShowImportDialog(false); setImportUrl(''); setImportPreview(null)
      void fetchSkills()
    } catch (e: any) { setImportError(e.message || '网络错误') } finally { setImportLoading(false) }
  }

  const handleDeleteSkill = async (skillId: string) => {
    if (!confirm('确定删除该技能？')) return
    try {
      const res = await fetch(`${apiBase}/teacher/skills/${encodeURIComponent(skillId)}`, { method: 'DELETE' })
      const data = await res.json()
      if (!data.ok) { alert(data.error || '删除失败'); return }
      void fetchSkills()
    } catch (e: any) { alert(e.message || '删除失败') }
  }

  const handleEditSkill = (skill: any) => {
    setEditingSkillId(skill.id); setEditTitle(skill.title || '')
    // Use instructions (full body) if available, fall back to desc (short description)
    setEditDesc(skill.instructions || skill.desc || '')
    setEditKeywords(Array.isArray(skill.keywords) ? skill.keywords.join('，') : '')
    setEditExamples(Array.isArray(skill.examples) ? skill.examples.join('\n') : '')
    setEditError('')
  }

  const handleSaveEdit = async () => {
    if (!editingSkillId) return
    setEditSaving(true); setEditError('')
    try {
      const body: any = {}
      if (editTitle.trim()) body.title = editTitle.trim()
      if (editDesc.trim()) body.description = editDesc.trim()
      // Always send keywords and examples so they can be cleared to empty
      body.keywords = editKeywords.trim() ? editKeywords.split(/[,，]/).map(s => s.trim()).filter(Boolean) : []
      body.examples = editExamples.trim() ? editExamples.split('\n').map(s => s.trim()).filter(Boolean) : []
      const res = await fetch(`${apiBase}/teacher/skills/${encodeURIComponent(editingSkillId)}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      })
      const data = await res.json()
      if (!data.ok) { setEditError(data.error || '更新失败'); return }
      setEditingSkillId(null); void fetchSkills()
    } catch (e: any) { setEditError(e.message || '网络错误') } finally { setEditSaving(false) }
  }

  return (
    <>
      <div className="flex items-center justify-between gap-[8px] flex-wrap mb-[12px]">
        <div className="flex-[1_1_180px] min-w-0">
          <input
            className="w-full"
            value={skillQuery}
            onChange={(e) => setSkillQuery(e.target.value)}
            placeholder="搜索技能"
          />
        </div>
        <div className="inline-flex items-center gap-[8px] flex-wrap">
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
          <label className="inline-flex items-center gap-[6px] text-[12px] text-muted whitespace-nowrap">
            <input
              type="checkbox"
              checked={showFavoritesOnly}
              onChange={(e) => setShowFavoritesOnly(e.target.checked)}
            />
            只看收藏
          </label>
        </div>
        <div className="inline-flex items-center gap-[8px] flex-wrap">
          <button type="button" className="ghost" onClick={() => { setShowCreateForm(v => !v); setShowImportDialog(false) }}>
            + 创建技能
          </button>
          <button type="button" className="ghost" onClick={() => { setShowImportDialog(v => !v); setShowCreateForm(false) }}>
            导入技能
          </button>
        </div>
      </div>
      {showCreateForm && (
        <div className="bg-surface-soft border border-border rounded-[8px] p-[12px] mb-[12px]">
          <h4 className="m-0 mb-[8px] text-[14px]">创建自定义技能</h4>
          <label className="block text-[12px] text-muted mt-[6px] mb-[2px]">标题（必填）</label>
          <input className="w-full py-[6px] px-[8px] border border-border rounded-[6px] text-[13px] bg-surface" value={createTitle} onChange={e => setCreateTitle(e.target.value)} placeholder="例如：课堂小测生成" />
          <label className="block text-[12px] text-muted mt-[6px] mb-[2px]">描述/指令（必填）</label>
          <textarea className="w-full py-[6px] px-[8px] border border-border rounded-[6px] text-[13px] bg-surface" value={createDesc} onChange={e => setCreateDesc(e.target.value)} rows={4} placeholder="技能的详细指令..." />
          <label className="block text-[12px] text-muted mt-[6px] mb-[2px]">关键词（逗号分隔，可选）</label>
          <input className="w-full py-[6px] px-[8px] border border-border rounded-[6px] text-[13px] bg-surface" value={createKeywords} onChange={e => setCreateKeywords(e.target.value)} placeholder="小测,课堂,生成" />
          <label className="block text-[12px] text-muted mt-[6px] mb-[2px]">示例 prompt（每行一条，可选）</label>
          <textarea className="w-full py-[6px] px-[8px] border border-border rounded-[6px] text-[13px] bg-surface" value={createExamples} onChange={e => setCreateExamples(e.target.value)} rows={2} placeholder="生成一份课堂小测" />
          {createError && <div className="status err">{createError}</div>}
          <div className="flex gap-[8px] mt-[8px]">
            <button type="button" onClick={handleCreateSkill} disabled={createSaving}>{createSaving ? '保存中…' : '保存'}</button>
            <button type="button" className="ghost" onClick={() => setShowCreateForm(false)}>取消</button>
          </div>
        </div>
      )}
      {showImportDialog && (
        <div className="bg-surface-soft border border-border rounded-[8px] p-[12px] mb-[12px]">
          <h4 className="m-0 mb-[8px] text-[14px]">从 GitHub 导入技能</h4>
          <label className="block text-[12px] text-muted mt-[6px] mb-[2px]">GitHub URL</label>
          <input className="w-full py-[6px] px-[8px] border border-border rounded-[6px] text-[13px] bg-surface" value={importUrl} onChange={e => setImportUrl(e.target.value)} placeholder="https://github.com/user/repo/tree/main/skill-name" />
          <div className="flex gap-[8px] mt-[8px]">
            <button type="button" className="ghost" onClick={handleImportPreview} disabled={importLoading}>预览</button>
            <button type="button" onClick={handleImportConfirm} disabled={importLoading || !importUrl.trim()}>{importLoading ? '导入中…' : '确认导入'}</button>
            <button type="button" className="ghost" onClick={() => setShowImportDialog(false)}>取消</button>
          </div>
          {importError && <div className="status err">{importError}</div>}
          {importPreview && (
            <div className="mt-[8px] p-[8px] bg-surface rounded-[6px] text-[13px]">
              <strong>{importPreview.title}</strong>
              {importPreview.desc && <p>{importPreview.desc}</p>}
              {importPreview.keywords?.length > 0 && <div className="muted">关键词：{importPreview.keywords.join('、')}</div>}
              {importPreview.preview && <pre className="status ok">{importPreview.preview}</pre>}
            </div>
          )}
        </div>
      )}
      {skillsLoading && <div className="text-[12px] text-muted mb-[8px]">正在加载技能...</div>}
      {skillsError && <div className="text-[12px] text-[#8a1f1f] mb-[8px]">{skillsError}</div>}
      <div className="skills-body grid gap-[12px] overflow-y-auto flex-1 min-h-0 pr-[4px]" style={{ overscrollBehavior: 'contain' }}>
        {filteredSkills.map((skill) => (
          <div key={skill.id} className={`skill-card border rounded-[14px] p-[12px] bg-white ${skillPinned && skill.id === activeSkillId ? 'border-accent shadow-[0_10px_20px_rgba(47,109,107,0.14)]' : 'border-border'}`}>
            <div className="flex justify-between items-baseline gap-[8px] mb-[6px]">
              <div>
                <strong>{skill.title}</strong>
                {skill.source_type === 'teacher' && <span className="inline-block text-[11px] text-accent bg-accent-soft py-[1px] px-[6px] rounded-[4px] ml-[6px] align-middle">[自建]</span>}
              </div>
              <button
                type="button"
                className={`border-none bg-transparent cursor-pointer text-[16px] ${favorites.includes(skill.id) ? 'text-[#d38b2f]' : 'text-muted'}`}
                onClick={() => toggleFavorite(skill.id)}
                aria-label="收藏技能"
              >
                {favorites.includes(skill.id) ? '★' : '☆'}
              </button>
            </div>
            <p className="m-0 mb-[10px] text-muted text-[13px]">{skill.desc}</p>
            <div className="flex gap-[8px] flex-wrap">
              <button
                type="button"
                className="border border-border rounded-[8px] bg-white text-[#334155] py-[5px] px-[10px] text-[12px] cursor-pointer"
                onClick={() => {
                  chooseSkill(skill.id, true)
                  setComposerWarning('')
                }}
              >
                设为当前
              </button>
              <button
                type="button"
                className="border border-border rounded-[8px] bg-white text-[#334155] py-[5px] px-[10px] text-[12px] cursor-pointer"
                onClick={() => {
                  chooseSkill(skill.id, true)
                  insertInvocationTokenAtCursor('skill', skill.id)
                }}
              >
                插入 $
              </button>
            </div>
            <div className="flex flex-wrap gap-[8px]">
              {skill.prompts.map((prompt: any) => (
                <button
                  key={prompt}
                  type="button"
                  className="border-none bg-[#e8f3f1] text-accent py-[6px] px-[10px] rounded-[8px] cursor-pointer text-[12px]"
                  onClick={() => {
                    chooseSkill(skill.id, true)
                    insertPrompt(prompt)
                  }}
                >
                  使用模板
                </button>
              ))}
            </div>
            <div className="flex flex-wrap gap-[8px]">
              {skill.examples.map((ex: any) => (
                <button
                  key={ex}
                  type="button"
                  className="border-none bg-[#f0f6f5] text-accent py-[6px] px-[10px] rounded-[8px] cursor-pointer text-[12px]"
                  onClick={() => {
                    chooseSkill(skill.id, true)
                    insertPrompt(ex)
                  }}
                >
                  {ex}
                </button>
              ))}
            </div>
            {skill.source_type === 'teacher' && (
              <div className="flex gap-[6px] mt-[6px] pt-[6px] border-t border-border">
                {editingSkillId === skill.id ? (
                  <div className="bg-surface-soft border border-border rounded-[8px] p-[12px] mb-[12px]">
                    <label className="block text-[12px] text-muted mt-[6px] mb-[2px]">标题</label>
                    <input className="w-full py-[6px] px-[8px] border border-border rounded-[6px] text-[13px] bg-surface" value={editTitle} onChange={e => setEditTitle(e.target.value)} />
                    <label className="block text-[12px] text-muted mt-[6px] mb-[2px]">描述</label>
                    <textarea className="w-full py-[6px] px-[8px] border border-border rounded-[6px] text-[13px] bg-surface" value={editDesc} onChange={e => setEditDesc(e.target.value)} rows={3} />
                    <label className="block text-[12px] text-muted mt-[6px] mb-[2px]">关键词（逗号分隔）</label>
                    <input className="w-full py-[6px] px-[8px] border border-border rounded-[6px] text-[13px] bg-surface" value={editKeywords} onChange={e => setEditKeywords(e.target.value)} />
                    <label className="block text-[12px] text-muted mt-[6px] mb-[2px]">示例（每行一条）</label>
                    <textarea className="w-full py-[6px] px-[8px] border border-border rounded-[6px] text-[13px] bg-surface" value={editExamples} onChange={e => setEditExamples(e.target.value)} rows={2} />
                    {editError && <div className="status err">{editError}</div>}
                    <div className="flex gap-[8px] mt-[8px]">
                      <button type="button" onClick={handleSaveEdit} disabled={editSaving}>{editSaving ? '保存中…' : '保存'}</button>
                      <button type="button" className="ghost" onClick={() => setEditingSkillId(null)}>取消</button>
                    </div>
                  </div>
                ) : (
                  <>
                    <button type="button" className="ghost" onClick={() => handleEditSkill(skill)}>编辑</button>
                    <button type="button" className="ghost" onClick={() => handleDeleteSkill(skill.id)}>删除</button>
                  </>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </>
  )
}
