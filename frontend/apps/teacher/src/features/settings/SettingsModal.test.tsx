import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import SettingsModal from './SettingsModal';

afterEach(() => {
  cleanup();
});

describe('SettingsModal', () => {
  it('role_dialog_is_on_inner_panel', () => {
    render(
      <SettingsModal
        open
        onClose={vi.fn()}
        sections={[{ id: 'general', label: '通用' }]}
        activeSection="general"
        onSectionChange={vi.fn()}
        title="设置"
      >
        <div>body</div>
      </SettingsModal>,
    );
    const dialog = screen.getByRole('dialog', { name: '设置' });
    expect(dialog.className).toContain('settings-dialog');
    expect(dialog.parentElement?.className).toContain('settings-overlay');
    expect(dialog.parentElement?.getAttribute('role')).toBeNull();
  });
});
