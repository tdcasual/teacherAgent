import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import StudentTopbar from './StudentTopbar';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const buildProps = () => ({
  verifiedStudent: null,
  sidebarOpen: false,
  homeActive: true,
  dispatch: vi.fn(),
  openTodayHome: vi.fn(),
  startNewStudentSession: vi.fn(),
});

describe('StudentTopbar compact mobile mode', () => {
  it('renders AI entry logo on desktop mode', () => {
    const props = buildProps();
    render(<StudentTopbar {...props} />);

    const logo = screen.getByAltText('AI入口图标');
    expect(logo.getAttribute('src')).toBe('/ai-entry-logo.png');
  });

  it('hides AI entry logo on compact mobile mode', () => {
    const props = buildProps();
    render(<StudentTopbar {...props} compactMobile />);

    expect(screen.queryByAltText('AI入口图标')).toBeNull();
  });

  it('uses compact labels and hides low-priority identity text', () => {
    const props = buildProps();
    render(<StudentTopbar {...props} compactMobile />);
    const header = screen.getByRole('banner');

    expect(screen.getByText('物理学习助手')).toBeTruthy();
    expect(screen.queryByText('物理学习助手 · 学生端')).toBeNull();
    expect(screen.getByRole('button', { name: '会话' })).toBeTruthy();
    expect(screen.getByRole('button', { name: '今日任务' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: '新建' })).toBeNull();
    expect(screen.getByRole('button', { name: '更多' })).toBeTruthy();
    expect(header.className).toContain('mobile-topbar-compact');
    expect(screen.queryByText('身份：学生')).toBeNull();
  });

  it('opens today homepage from the task-priority action', () => {
    const props = buildProps();
    render(<StudentTopbar {...props} compactMobile homeActive={false} />);

    fireEvent.click(screen.getByRole('button', { name: '今日任务' }));

    expect(props.openTodayHome).toHaveBeenCalledTimes(1);
  });

  it('shows compact quick actions menu', () => {
    const props = buildProps();
    render(<StudentTopbar {...props} compactMobile />);

    fireEvent.click(screen.getByRole('button', { name: '更多' }));

    expect(screen.getByRole('menu', { name: '移动端更多操作' })).toBeTruthy();
    expect(screen.getByText('未验证学生身份')).toBeTruthy();
  });
});
