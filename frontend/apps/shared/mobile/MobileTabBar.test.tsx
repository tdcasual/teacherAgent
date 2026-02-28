import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MobileTabBar } from './MobileTabBar';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('MobileTabBar', () => {
  it('marks the active tab with tab semantics', () => {
    render(
      <MobileTabBar
        items={[
          { id: 'chat', label: '聊天' },
          { id: 'sessions', label: '会话' },
        ]}
        activeId="sessions"
        onChange={() => {}}
      />,
    );

    const active = screen.getByRole('tab', { name: '会话' });
    const inactive = screen.getByRole('tab', { name: '聊天' });
    expect(active.getAttribute('aria-current')).toBe('page');
    expect(active.getAttribute('aria-selected')).toBe('true');
    expect(active.getAttribute('tabindex')).toBe('0');
    expect(inactive.getAttribute('aria-selected')).toBe('false');
    expect(inactive.getAttribute('tabindex')).toBe('-1');
  });

  it('calls onChange when clicking a tab', () => {
    const onChange = vi.fn();
    render(
      <MobileTabBar
        items={[
          { id: 'chat', label: '聊天' },
          { id: 'sessions', label: '会话' },
          { id: 'learning', label: '学习' },
        ]}
        activeId="chat"
        onChange={onChange}
      />,
    );

    fireEvent.click(screen.getByRole('tab', { name: '学习' }));
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith('learning');
  });

  it('supports keyboard arrow navigation', () => {
    const onChange = vi.fn();
    render(
      <MobileTabBar
        items={[
          { id: 'chat', label: '聊天' },
          { id: 'sessions', label: '会话' },
          { id: 'learning', label: '学习' },
        ]}
        activeId="chat"
        onChange={onChange}
      />,
    );

    const chatTab = screen.getByRole('tab', { name: '聊天' });
    chatTab.focus();
    fireEvent.keyDown(chatTab, { key: 'ArrowRight' });
    fireEvent.keyDown(chatTab, { key: 'End' });

    expect(onChange).toHaveBeenCalledWith('sessions');
    expect(onChange).toHaveBeenCalledWith('learning');
  });

  it('renders decorative icons without affecting tab accessible labels', () => {
    render(
      <MobileTabBar
        items={[
          {
            id: 'chat',
            label: '聊天',
            icon: (
              <svg data-testid="chat-icon" viewBox="0 0 16 16">
                <circle cx="8" cy="8" r="7" />
              </svg>
            ),
          },
          { id: 'sessions', label: '会话' },
        ]}
        activeId="chat"
        onChange={() => {}}
      />,
    );

    const tab = screen.getByRole('tab', { name: '聊天' });
    expect(tab.querySelector('.mobile-tabbar-icon')?.getAttribute('aria-hidden')).toBe('true');
    expect(screen.getByTestId('chat-icon')).toBeTruthy();
  });
});
