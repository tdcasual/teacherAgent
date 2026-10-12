import { createRef } from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import ChatPanel from './ChatPanel';

vi.mock('./ChatMessages', () => ({
  default: () => <div>messages</div>,
}));
vi.mock('./ChatComposer', () => ({
  default: () => <div>composer</div>,
}));

afterEach(() => {
  cleanup();
});

const baseProps = {
  renderedMessages: [],
  sending: false,
  pendingChatJobId: '',
  verifiedStudent: { student_id: 'S1', student_name: '甲' },
  messagesRef: createRef<HTMLDivElement>(),
  endRef: createRef<HTMLDivElement>(),
  isNearBottom: true,
  scrollToBottom: vi.fn(),
  inputRef: createRef<HTMLTextAreaElement>(),
  input: '',
  setInput: vi.fn(),
  handleInputKeyDown: vi.fn(),
  handleSend: vi.fn(),
  composerHint: '',
  attachments: [],
  uploadingAttachments: false,
  hasSendableAttachments: false,
  onPickFiles: vi.fn(),
  onRemoveAttachment: vi.fn(),
};

describe('ChatPanel submit copy', () => {
  it('uses submitActionLabel from selected assignment kind', () => {
    const { rerender } = render(
      <ChatPanel {...baseProps} onOpenSubmit={() => undefined} assignmentKind="practical" />,
    );
    expect(screen.getByRole('button', { name: '提交实践照片' })).toBeTruthy();

    rerender(<ChatPanel {...baseProps} onOpenSubmit={() => undefined} assignmentKind="scenario" />);
    expect(screen.getByRole('button', { name: '提交书面/照片' })).toBeTruthy();

    rerender(
      <ChatPanel {...baseProps} onOpenSubmit={() => undefined} assignmentKind="problem_set" />,
    );
    expect(screen.getByRole('button', { name: '提交作业' })).toBeTruthy();
  });

  it('hides submit bar when onOpenSubmit is missing', () => {
    render(<ChatPanel {...baseProps} />);
    expect(screen.queryByRole('button', { name: '提交作业' })).toBeNull();
  });
});
