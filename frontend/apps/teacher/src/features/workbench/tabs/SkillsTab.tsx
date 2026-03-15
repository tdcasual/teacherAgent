import type { Skill } from '../../../appTypes'
import type { InvocationTriggerType } from '../../chat/invocation'

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
  insertInvocationTokenAtCursor: (type: InvocationTriggerType, id: string) => void
  stopKeyPropagation: (e: React.KeyboardEvent<HTMLElement>) => void
  setSkillQuery: (q: string) => void
  setShowFavoritesOnly: (v: boolean) => void
  setSkillPinned: (v: boolean) => void
  setComposerWarning: (msg: string) => void
}

export default function SkillsTab(props: SkillsTabProps) {
  const {
    filteredSkills,
    favorites,
    activeSkillId,
    skillPinned,
    skillQuery,
    showFavoritesOnly,
    skillsLoading,
    skillsError,
    chooseSkill,
    toggleFavorite,
    insertPrompt,
    insertInvocationTokenAtCursor,
    setSkillQuery,
    setShowFavoritesOnly,
    setSkillPinned,
    setComposerWarning,
  } = props

  return (
    <>
      <div className="flex items-center justify-between gap-[8px] flex-wrap mb-[12px]">
        <div className="flex-[1_1_180px] min-w-0">
          <input
            className="w-full"
            value={skillQuery}
            onChange={(event) => setSkillQuery(event.target.value)}
            placeholder="搜索教学能力"
          />
        </div>
        <div className="inline-flex items-center gap-[8px] flex-wrap">
          <button
            type="button"
            className="ghost"
            disabled={!skillPinned}
            onClick={() => {
              setSkillPinned(false)
              setComposerWarning('已切换到自动工作流推荐（未显式指定时由后端自动选择）。')
            }}
          >
            切回自动推荐
          </button>
          <label className="inline-flex items-center gap-[6px] text-[12px] text-muted whitespace-nowrap">
            <input
              type="checkbox"
              checked={showFavoritesOnly}
              onChange={(event) => setShowFavoritesOnly(event.target.checked)}
            />
            只看收藏
          </label>
        </div>
      </div>

      <div className="mb-[10px] rounded-[12px] border border-[color:color-mix(in_oklab,var(--color-border)_78%,white)] bg-[color:color-mix(in_oklab,var(--color-panel)_88%,white)] px-[10px] py-[8px] text-[12px] text-muted">
        当前仅保留系统内置教学能力，可直接选择或让系统自动推荐。
      </div>

      {skillsLoading ? <div className="text-[12px] text-muted mb-[8px]">正在加载能力...</div> : null}
      {skillsError ? <div className="text-[12px] text-[#8a1f1f] mb-[8px]">{skillsError}</div> : null}

      <div className="skills-body grid gap-[12px] overflow-y-auto flex-1 min-h-0 pr-[4px]" style={{ overscrollBehavior: 'contain' }}>
        {filteredSkills.map((skill) => (
          <div
            key={skill.id}
            className={`skill-card border rounded-[16px] p-[12px] ${skillPinned && skill.id === activeSkillId
              ? 'border-[color:color-mix(in_oklab,var(--color-accent)_70%,white)] bg-[linear-gradient(180deg,color-mix(in_oklab,var(--color-accent-soft)_68%,white)_0%,white_100%)] shadow-[0_10px_20px_rgba(66,81,120,0.12)]'
              : 'border-[color:color-mix(in_oklab,var(--color-border)_78%,white)] bg-[color:color-mix(in_oklab,var(--color-surface)_94%,white)] shadow-none'}`}
          >
            <div className="flex justify-between items-baseline gap-[8px] mb-[6px]">
              <div>
                <strong>{skill.title}</strong>
                {skill.source_type === 'teacher' ? (
                  <span className="inline-block text-[11px] text-muted bg-surface-soft py-[1px] px-[6px] rounded-[4px] ml-[6px] align-middle">[只读]</span>
                ) : null}
              </div>
              <button
                type="button"
                className={`border-none bg-transparent cursor-pointer text-[16px] ${favorites.includes(skill.id) ? 'text-[#d38b2f]' : 'text-muted'}`}
                onClick={() => toggleFavorite(skill.id)}
                aria-label="收藏能力"
              >
                {favorites.includes(skill.id) ? '★' : '☆'}
              </button>
            </div>

            <p className="m-0 mb-[10px] text-muted text-[13px]">{skill.desc}</p>

            <div className="flex gap-[8px] flex-wrap mb-[8px]">
              <button
                type="button"
                className="teacher-drawer-link"
                onClick={() => {
                  chooseSkill(skill.id, true)
                  setComposerWarning('')
                }}
              >
                设为当前
              </button>
              <button
                type="button"
                className="teacher-drawer-link"
                onClick={() => {
                  chooseSkill(skill.id, true)
                  insertInvocationTokenAtCursor('skill', skill.id)
                }}
              >
                插入 $
              </button>
            </div>

            <div className="flex flex-wrap gap-[8px]">
              {skill.prompts.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  className="rounded-[999px] border border-[color:color-mix(in_oklab,var(--color-accent)_20%,white)] bg-[color:color-mix(in_oklab,var(--color-accent-soft)_62%,white)] py-[6px] px-[10px] text-[12px] text-accent cursor-pointer"
                  onClick={() => {
                    chooseSkill(skill.id, true)
                    insertPrompt(prompt)
                  }}
                >
                  使用模板
                </button>
              ))}
            </div>

            <div className="flex flex-wrap gap-[8px] mt-[6px]">
              {skill.examples.map((example) => (
                <button
                  key={example}
                  type="button"
                  className="rounded-[999px] border border-[color:color-mix(in_oklab,var(--color-border)_74%,white)] bg-[color:color-mix(in_oklab,var(--color-panel)_86%,white)] py-[6px] px-[10px] text-[12px] text-muted cursor-pointer"
                  onClick={() => {
                    chooseSkill(skill.id, true)
                    insertPrompt(example)
                  }}
                >
                  {example}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </>
  )
}
