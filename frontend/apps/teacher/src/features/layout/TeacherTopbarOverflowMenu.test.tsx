import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { createRef } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import TeacherTopbarOverflowMenu from './TeacherTopbarOverflowMenu';

afterEach(() => {
  cleanup();
});

describe('TeacherTopbarOverflowMenu', () => {
  it('menu_items_have_menuitem_role', () => {
    render(
      <TeacherTopbarOverflowMenu
        skillsOpen={false}
        authOpen={false}
        authButtonRef={createRef<HTMLButtonElement>()}
        onToggleAuth={vi.fn()}
        onToggleSkillsWorkbench={vi.fn()}
        onToggleSettingsPanel={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: '更多' }));
    const items = screen.getAllByRole('menuitem');
    expect(items.length).toBeGreaterThanOrEqual(3);
  });
});
