import { afterEach, describe, expect, it } from 'vitest';
import { getFocusableElements, trapFocusOnTab } from './focusTrap';

afterEach(() => {
  document.body.replaceChildren();
});

describe('focusTrap', () => {
  it('lists enabled tabbable controls and skips disabled ones', () => {
    const root = document.createElement('div');
    root.innerHTML = `
      <button type="button">one</button>
      <button type="button" disabled>nope</button>
      <input />
      <a href="#x">link</a>
      <div tabindex="-1">skip</div>
    `;
    document.body.append(root);
    const focusable = getFocusableElements(root);
    expect(focusable.map((element) => element.tagName)).toEqual(['BUTTON', 'INPUT', 'A']);
  });

  it('cycles Tab from last to first and Shift+Tab from first to last', () => {
    const root = document.createElement('div');
    const first = document.createElement('button');
    const last = document.createElement('button');
    first.textContent = 'first';
    last.textContent = 'last';
    root.append(first, last);
    document.body.append(root);
    last.focus();

    trapFocusOnTab(
      new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true }),
      root,
    );
    expect(document.activeElement).toBe(first);

    first.focus();
    trapFocusOnTab(
      new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true, shiftKey: true }),
      root,
    );
    expect(document.activeElement).toBe(last);
  });

  it('prevents Tab when nothing is focusable', () => {
    const root = document.createElement('div');
    document.body.append(root);
    const event = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true });
    trapFocusOnTab(event, root);
    expect(event.defaultPrevented).toBe(true);
  });

  it('ignores non-Tab keys', () => {
    const event = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true });
    trapFocusOnTab(event, document.body);
    expect(event.defaultPrevented).toBe(false);
  });
});
