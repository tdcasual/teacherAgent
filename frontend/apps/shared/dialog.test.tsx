import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { ConfirmDialog, PromptDialog } from './dialog';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('ConfirmDialog', () => {
  it('calls onCancel when pressing escape', () => {
    const onCancel = vi.fn();
    render(
      <ConfirmDialog
        open
        title="删除会话"
        confirmText="删除"
        onConfirm={() => {}}
        onCancel={onCancel}
      />,
    );
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('traps tab focus inside the dialog', async () => {
    render(
      <ConfirmDialog
        open
        title="删除会话"
        confirmText="删除"
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    );
    const cancelButton = screen.getByRole('button', { name: '取消' });
    const confirmButton = screen.getByRole('button', { name: '删除' });

    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(document.activeElement).toBe(confirmButton);

    fireEvent.keyDown(document, { key: 'Tab' });
    expect(document.activeElement).toBe(cancelButton);
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });
    expect(document.activeElement).toBe(confirmButton);
  });
});

describe('PromptDialog', () => {
  it('associates the field label with the input via htmlFor', () => {
    render(<PromptDialog open title="重命名" onConfirm={() => {}} onCancel={() => {}} />);
    const input = screen.getByPlaceholderText('请输入…');
    expect(screen.getByLabelText('会话名称')).toBe(input);
    expect(input.id).toBeTruthy();
    expect(input.id).toBe(screen.getByText('会话名称').closest('label')?.htmlFor);
  });

  it('traps tab focus from last action back to the input', async () => {
    render(<PromptDialog open title="重命名" onConfirm={() => {}} onCancel={() => {}} />);
    const input = screen.getByLabelText('会话名称');
    const confirmButton = screen.getByRole('button', { name: '保存' });

    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(document.activeElement).toBe(input);

    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });
    expect(document.activeElement).toBe(confirmButton);
    fireEvent.keyDown(document, { key: 'Tab' });
    expect(document.activeElement).toBe(input);
  });
});
