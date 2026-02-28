import { useEffect, useId, useRef, type ReactNode } from 'react';

type BottomSheetProps = {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
};

export function BottomSheet({
  open,
  onClose,
  title = '面板',
  children,
  footer,
  className = '',
}: BottomSheetProps) {
  const titleId = useId();
  const panelRef = useRef<HTMLElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const lastFocusedRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    lastFocusedRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    window.setTimeout(() => closeButtonRef.current?.focus(), 0);

    const getFocusableElements = () => {
      const panel = panelRef.current;
      if (!panel) return [] as HTMLElement[];
      return Array.from(
        panel.querySelectorAll<HTMLElement>(
          'button,[href],input,select,textarea,[tabindex]:not([tabindex="-1"])',
        ),
      ).filter((element) => !element.hasAttribute('disabled'));
    };

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
        return;
      }
      if (event.key !== 'Tab') return;
      const focusable = getFocusableElements();
      if (!focusable.length) {
        event.preventDefault();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const activeElement = document.activeElement as HTMLElement | null;
      if (event.shiftKey) {
        if (activeElement === first || !activeElement) {
          event.preventDefault();
          last.focus();
        }
        return;
      }
      if (activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = previousOverflow;
      lastFocusedRef.current?.focus();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="mobile-sheet-layer">
      <button
        type="button"
        className="mobile-sheet-overlay"
        data-testid="mobile-sheet-overlay"
        aria-label="关闭面板"
        onClick={onClose}
      />
      <section
        ref={panelRef}
        className={`mobile-sheet-panel ${className}`.trim()}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <header className="mobile-sheet-header">
          <h2 id={titleId} className="mobile-sheet-title">
            {title}
          </h2>
          <button
            ref={closeButtonRef}
            type="button"
            className="mobile-sheet-close"
            aria-label="关闭"
            onClick={onClose}
          >
            关闭
          </button>
        </header>
        <div className="mobile-sheet-body">{children}</div>
        {footer ? <footer className="mobile-sheet-footer">{footer}</footer> : null}
      </section>
    </div>
  );
}
