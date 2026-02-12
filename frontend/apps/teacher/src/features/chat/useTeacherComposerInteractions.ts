import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type Dispatch,
  type FormEvent,
  type KeyboardEvent,
  type MutableRefObject,
  type SetStateAction,
} from 'react'
import { buildInvocationToken, findInvocationTrigger, type InvocationTriggerType } from './invocation'
import type { MentionOption, PendingChatJob, Skill } from '../../appTypes'

type UseTeacherComposerInteractionsParams = {
  input: string
  setInput: (value: string) => void
  cursorPos: number
  setCursorPos: (value: number) => void
  inputRef: MutableRefObject<HTMLTextAreaElement | null>
  skillList: Skill[]
  skillQuery: string
  showFavoritesOnly: boolean
  favorites: string[]
  activeSkillId: string
  setActiveSkillId: (value: string) => void
  setSkillPinned: (value: boolean) => void
  chooseSkill: (skillId: string, pinned?: boolean) => void
  setFavorites: Dispatch<SetStateAction<string[]>>
  submitMessage: (inputText: string) => Promise<void>
  pendingChatJob: PendingChatJob | null
  sending: boolean
}

export function useTeacherComposerInteractions(params: UseTeacherComposerInteractionsParams) {
  const {
    input,
    setInput,
    cursorPos,
    setCursorPos,
    inputRef,
    skillList,
    skillQuery,
    showFavoritesOnly,
    favorites,
    activeSkillId,
    setActiveSkillId,
    setSkillPinned,
    chooseSkill,
    setFavorites,
    submitMessage,
    pendingChatJob,
    sending,
  } = params

  const [mentionIndex, setMentionIndex] = useState(0)

  const mention = useMemo(() => {
    const trigger = findInvocationTrigger(input, cursorPos)
    if (!trigger) return null
    const query = trigger.query
    const source: MentionOption[] = skillList.map((skill) => ({
      id: skill.id,
      title: skill.title,
      desc: skill.desc,
      type: 'skill' as const,
    }))
    const items = source.filter(
      (item) =>
        item.title.toLowerCase().includes(query) ||
        item.desc.toLowerCase().includes(query) ||
        item.id.toLowerCase().includes(query),
    )
    return { start: trigger.start, query, type: trigger.type, items }
  }, [cursorPos, input, skillList])

  const mentionItemIds = mention?.items.map((item) => item.id).join(',') ?? ''
  useEffect(() => {
    if (mention && mention.items.length) {
      setMentionIndex(0)
    }
  }, [mentionItemIds, mention])

  const filteredSkills = useMemo(() => {
    const query = skillQuery.trim().toLowerCase()
    let list = skillList.filter((skill) => {
      if (!query) return true
      return (
        skill.id.toLowerCase().includes(query) ||
        skill.title.toLowerCase().includes(query) ||
        skill.desc.toLowerCase().includes(query)
      )
    })
    if (showFavoritesOnly) {
      list = list.filter((skill) => favorites.includes(skill.id))
    }
    return list.sort((a, b) => {
      const aFav = favorites.includes(a.id)
      const bFav = favorites.includes(b.id)
      if (aFav === bFav) return a.title.localeCompare(b.title)
      return aFav ? -1 : 1
    })
  }, [skillQuery, showFavoritesOnly, favorites, skillList])

  const activeSkill = useMemo(() => {
    if (!activeSkillId) return null
    return skillList.find((item) => item.id === activeSkillId) || null
  }, [activeSkillId, skillList])

  useEffect(() => {
    if (!activeSkillId) {
      setActiveSkillId('physics-teacher-ops')
      setSkillPinned(false)
      return
    }
    if (!activeSkill) {
      setActiveSkillId('physics-teacher-ops')
      setSkillPinned(false)
    }
  }, [activeSkillId, activeSkill, setActiveSkillId, setSkillPinned])

  const stopKeyPropagation = useCallback((event: KeyboardEvent<HTMLElement>) => {
    event.stopPropagation()
  }, [])

  const insertPrompt = useCallback(
    (prompt: string) => {
      const nextValue = input ? `${input}\n${prompt}` : prompt
      setInput(nextValue)
      requestAnimationFrame(() => {
        if (!inputRef.current) return
        inputRef.current.focus()
        inputRef.current.setSelectionRange(nextValue.length, nextValue.length)
        setCursorPos(nextValue.length)
      })
    },
    [input, inputRef, setCursorPos, setInput],
  )

  const insertInvocationTokenAtCursor = useCallback(
    (type: InvocationTriggerType, id: string) => {
      const token = buildInvocationToken(type, id)
      if (!token) return
      const before = input.slice(0, cursorPos)
      const after = input.slice(cursorPos)
      const leading = before && !/\s$/.test(before) ? ' ' : ''
      const trailing = after && !/^\s/.test(after) ? ' ' : ''
      const nextValue = `${before}${leading}${token}${trailing}${after}`
      const nextPos = (before + leading + token).length
      setInput(nextValue)
      setCursorPos(nextPos)

      const el = inputRef.current
      if (el) {
        try {
          el.value = nextValue
          el.focus()
          el.setSelectionRange(nextPos, nextPos)
        } catch {
          // ignore selection errors
        }
      }
    },
    [cursorPos, input, inputRef, setCursorPos, setInput],
  )

  const insertMention = useCallback(
    (item: MentionOption) => {
      if (!mention) return
      const token = buildInvocationToken(item.type, item.id)
      if (!token) return
      chooseSkill(item.id, true)
      const before = input.slice(0, mention.start)
      const after = input.slice(cursorPos)
      const nextValue = `${before}${token} ${after}`.replace(/\s+$/, ' ')
      const nextPos = `${before}${token} `.length
      setInput(nextValue)
      setCursorPos(nextPos)

      const el = inputRef.current
      if (el) {
        try {
          el.value = nextValue
          el.focus()
          el.setSelectionRange(nextPos, nextPos)
        } catch {
          // ignore selection errors
        }
      }
    },
    [chooseSkill, cursorPos, input, inputRef, mention, setCursorPos, setInput],
  )

  const toggleFavorite = useCallback(
    (skillId: string) => {
      setFavorites((prev) => (prev.includes(skillId) ? prev.filter((id) => id !== skillId) : [...prev, skillId]))
    },
    [setFavorites],
  )

  const handleSend = useCallback(
    async (event: FormEvent) => {
      event.preventDefault()
      if (sending) return
      await submitMessage(input.trim())
    },
    [sending, submitMessage, input],
  )

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLTextAreaElement>) => {
      if (mention && mention.items.length) {
        if (event.key === 'ArrowDown') {
          event.preventDefault()
          setMentionIndex((prev) => (prev + 1) % mention.items.length)
          return
        }
        if (event.key === 'ArrowUp') {
          event.preventDefault()
          setMentionIndex((prev) => (prev - 1 + mention.items.length) % mention.items.length)
          return
        }
        if (event.key === 'Enter' && !event.shiftKey) {
          if (event.nativeEvent.isComposing) return
          event.preventDefault()
          const item = mention.items[mentionIndex]
          if (item) insertMention(item)
          return
        }
      }

      if (event.key === 'Enter' && !event.shiftKey) {
        if (event.nativeEvent.isComposing) return
        event.preventDefault()
        if (!input.trim()) return
        if (pendingChatJob?.job_id || sending) return
        void submitMessage(input.trim())
      }
    },
    [mention, mentionIndex, insertMention, input, pendingChatJob?.job_id, sending, submitMessage],
  )

  return {
    mention,
    mentionIndex,
    filteredSkills,
    stopKeyPropagation,
    insertPrompt,
    insertInvocationTokenAtCursor,
    insertMention,
    toggleFavorite,
    handleSend,
    handleKeyDown,
  }
}
