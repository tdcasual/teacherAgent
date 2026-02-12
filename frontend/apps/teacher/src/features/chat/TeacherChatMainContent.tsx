import type {
  FormEvent,
  KeyboardEvent,
  MutableRefObject,
} from 'react'
import RoutingPage from '../routing/RoutingPage'
import ChatComposer from './ChatComposer'
import ChatMessages from './ChatMessages'
import MentionPanel from './MentionPanel'
import type { MentionOption } from '../../appTypes'
import type { InvocationTriggerType } from './invocation'

type MentionState = {
  start: number
  query: string
  type: InvocationTriggerType
  items: MentionOption[]
} | null

type RenderedMessage = {
  id: string
  role: 'user' | 'assistant'
  html: string
  time: string
}

type TeacherChatMainContentProps = {
  inlineRoutingOpen: boolean
  apiBase: string
  onApiBaseChange: (value: string) => void
  onDirtyChange: (dirty: boolean) => void
  renderedMessages: RenderedMessage[]
  sending: boolean
  hasPendingChatJob: boolean
  typingTimeLabel: string
  messagesRef: MutableRefObject<HTMLDivElement | null>
  onMessagesScroll: () => void
  showScrollToBottom: boolean
  onScrollToBottom: () => void
  activeSkillId: string
  skillPinned: boolean
  input: string
  chatQueueHint: string
  composerWarning: string
  inputRef: MutableRefObject<HTMLTextAreaElement | null>
  onSubmit: (event: FormEvent) => void | Promise<void>
  onInputChange: (value: string, selectionStart: number) => void
  onInputClick: (selectionStart: number) => void
  onInputKeyUp: (selectionStart: number) => void
  onInputKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void
  mention: MentionState
  mentionIndex: number
  onInsertMention: (item: MentionOption) => void
}

export default function TeacherChatMainContent({
  inlineRoutingOpen,
  apiBase,
  onApiBaseChange,
  onDirtyChange,
  renderedMessages,
  sending,
  hasPendingChatJob,
  typingTimeLabel,
  messagesRef,
  onMessagesScroll,
  showScrollToBottom,
  onScrollToBottom,
  activeSkillId,
  skillPinned,
  input,
  chatQueueHint,
  composerWarning,
  inputRef,
  onSubmit,
  onInputChange,
  onInputClick,
  onInputKeyUp,
  onInputKeyDown,
  mention,
  mentionIndex,
  onInsertMention,
}: TeacherChatMainContentProps) {
  return (
    <main
      className={`chat-shell flex-auto w-full min-w-0 min-h-0 flex flex-col gap-[10px] p-4 overflow-hidden bg-surface ${inlineRoutingOpen ? 'overflow-auto' : ''}`}
      style={inlineRoutingOpen ? { overscrollBehavior: 'contain' } : undefined}
    >
      {inlineRoutingOpen ? (
        <RoutingPage
          apiBase={apiBase}
          onApiBaseChange={onApiBaseChange}
          onDirtyChange={onDirtyChange}
          section="general"
          legacyFlat
        />
      ) : (
        <>
          <ChatMessages
            renderedMessages={renderedMessages}
            sending={sending}
            hasPendingChatJob={hasPendingChatJob}
            typingTimeLabel={typingTimeLabel}
            messagesRef={messagesRef}
            onMessagesScroll={onMessagesScroll}
            showScrollToBottom={showScrollToBottom}
            onScrollToBottom={onScrollToBottom}
          />

          <ChatComposer
            activeSkillId={activeSkillId || 'physics-teacher-ops'}
            skillPinned={skillPinned}
            input={input}
            pendingChatJob={hasPendingChatJob}
            sending={sending}
            chatQueueHint={chatQueueHint}
            composerWarning={composerWarning}
            inputRef={inputRef}
            onSubmit={onSubmit}
            onInputChange={onInputChange}
            onInputClick={onInputClick}
            onInputKeyUp={onInputKeyUp}
            onInputKeyDown={onInputKeyDown}
          />

          <MentionPanel mention={mention} mentionIndex={mentionIndex} onInsert={onInsertMention} />
        </>
      )}
    </main>
  )
}
