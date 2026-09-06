const FOCUSABLE_SELECTOR = 'button,[href],input,select,textarea,[tabindex]:not([tabindex="-1"])';

export function getFocusableElements(root: HTMLElement | null): HTMLElement[] {
  if (!root) return [];
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
    (element) =>
      !element.hasAttribute('disabled') && element.getAttribute('aria-hidden') !== 'true',
  );
}

export function trapFocusOnTab(event: KeyboardEvent, root: HTMLElement | null): void {
  if (event.key !== 'Tab') return;
  const focusable = getFocusableElements(root);
  if (!focusable.length) {
    event.preventDefault();
    return;
  }
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  const activeElement = document.activeElement as HTMLElement | null;
  const activeIndex = activeElement ? focusable.indexOf(activeElement) : -1;
  if (event.shiftKey) {
    if (activeIndex <= 0) {
      event.preventDefault();
      last.focus();
    }
    return;
  }
  if (activeIndex === -1 || activeIndex === focusable.length - 1) {
    event.preventDefault();
    first.focus();
  }
}
