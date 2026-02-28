import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import StudentTopbar from './StudentTopbar';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const buildProps = () => ({
  apiBase: 'http://localhost:8000',
  verifiedStudent: null,
  sidebarOpen: false,
  dispatch: vi.fn(),
  startNewStudentSession: vi.fn(),
  personaEnabled: false,
  personaPickerOpen: false,
  personaCards: [],
  activePersonaId: '',
  personaLoading: false,
  personaError: '',
  onTogglePersonaEnabled: vi.fn(),
  onTogglePersonaPicker: vi.fn(),
  onSelectPersona: vi.fn(),
  onCreateCustomPersona: vi.fn(async () => {}),
  onUpdateCustomPersona: vi.fn(async () => {}),
  onUploadCustomPersonaAvatar: vi.fn(async () => {}),
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
    expect(screen.getByRole('button', { name: '新建' })).toBeTruthy();
    expect(screen.getByRole('button', { name: '更多' })).toBeTruthy();
    expect(header.className).toContain('mobile-topbar-compact');
    expect(screen.queryByText('身份：学生')).toBeNull();
    expect(screen.queryByRole('button', { name: '角色卡：关' })).toBeNull();
    expect(screen.queryByRole('button', { name: '选择角色卡' })).toBeNull();
  });

  it('moves persona actions into compact more menu', () => {
    const props = buildProps();
    render(<StudentTopbar {...props} compactMobile />);

    fireEvent.click(screen.getByRole('button', { name: '更多' }));

    expect(screen.getByRole('menu', { name: '移动端更多操作' })).toBeTruthy();
    expect(screen.getByRole('button', { name: '角色卡：关' })).toBeTruthy();
    expect(screen.getByRole('button', { name: '选择角色卡' })).toBeTruthy();
  });
});
