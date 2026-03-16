import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import TeacherChatMainContent from './TeacherChatMainContent'

vi.mock('./ChatMessages', () => ({
  default: () => <div>chat-messages</div>,
}))

vi.mock('./ChatComposer', () => ({
  default: () => <div>chat-composer</div>,
}))

vi.mock('./MentionPanel', () => ({
  default: () => null,
}))

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('TeacherChatMainContent', () => {
  it('wraps the desktop conversation in a focused stage shell', () => {
    render(
      <TeacherChatMainContent
        taskStrip={<div>task-strip</div>}
        renderedMessages={[]}
        sending={false}
        hasPendingChatJob={false}
        typingTimeLabel="10:00"
        messagesRef={{ current: null }}
        onMessagesScroll={() => undefined}
        showScrollToBottom={false}
        onScrollToBottom={() => undefined}
        activeSkillId="physics-teacher-ops"
        skillPinned={false}
        input=""
        chatQueueHint=""
        pendingStreamStage=""
        pendingToolRuns={[]}
        composerWarning=""
        attachments={[]}
        uploadingAttachments={false}
        hasSendableAttachments={false}
        inputRef={{ current: null }}
        onSubmit={() => undefined}
        onInputChange={() => undefined}
        onInputClick={() => undefined}
        onInputKeyUp={() => undefined}
        onInputKeyDown={() => undefined}
        onPickFiles={() => undefined}
        onRemoveAttachment={() => undefined}
        mention={null}
        mentionIndex={0}
        onInsertMention={() => undefined}
      />,
    )

    expect(screen.getByText('task-strip')).toBeTruthy()
    expect(screen.getByTestId('teacher-chat-stage').getAttribute('data-chat-stage-tone')).toBe(
      'focused',
    )
    expect(screen.getByText('chat-messages')).toBeTruthy()
    expect(screen.getByText('chat-composer')).toBeTruthy()
  })
})
