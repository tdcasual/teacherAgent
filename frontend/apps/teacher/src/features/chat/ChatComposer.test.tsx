import { cleanup, render, screen } from '@testing-library/react'
import { createRef } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import ChatComposer from './ChatComposer'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('ChatComposer copy', () => {
  it('surfaces workflow capability wording for automatic routing', () => {
    render(
      <ChatComposer
        activeSkillId="physics-teacher-ops"
        skillPinned={false}
        input=""
        pendingChatJob={false}
        sending={false}
        chatQueueHint=""
        composerWarning=""
        attachments={[]}
        uploadingAttachments={false}
        hasSendableAttachments={false}
        inputRef={{ current: null }}
        onSubmit={(event) => event.preventDefault()}
        onInputChange={() => undefined}
        onInputClick={() => undefined}
        onInputKeyUp={() => undefined}
        onInputKeyDown={() => undefined}
        onPickFiles={async () => undefined}
        onRemoveAttachment={async () => undefined}
      />,
    )

    expect(screen.getByText('当前路由: 自动编排')).toBeTruthy()
    expect(screen.getByPlaceholderText('输入教学指令、审阅要求或追问，使用 $ 查看能力。回车发送，Shift+Enter 换行')).toBeTruthy()
    expect(screen.getByText('工作流指令 | 回车发送')).toBeTruthy()
  })

  it('shows pinned capability label when a workflow is explicitly chosen', () => {
    render(
      <ChatComposer
        activeSkillId="physics-homework-generator"
        skillPinned
        input="生成一份作业"
        pendingChatJob={false}
        sending={false}
        chatQueueHint=""
        composerWarning=""
        attachments={[]}
        uploadingAttachments={false}
        hasSendableAttachments
        inputRef={createRef()}
        onSubmit={(event) => event.preventDefault()}
        onInputChange={() => undefined}
        onInputClick={() => undefined}
        onInputKeyUp={() => undefined}
        onInputKeyDown={() => undefined}
        onPickFiles={async () => undefined}
        onRemoveAttachment={async () => undefined}
      />,
    )

    expect(screen.getByText('当前路由: $physics-homework-generator')).toBeTruthy()
  })
})
