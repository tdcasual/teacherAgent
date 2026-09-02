import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { trapFocusOnTab } from './focusTrap';

type DialogFrameProps = {
  open: boolean;
  title: string;
  description?: string;
  onCancel: () => void;
  children: ReactNode;
  initialFocusRef?: React.RefObject<HTMLElement | null>;
};

function DialogFrame({
  open,
  title,
  description,
  onCancel,
  children,
  initialFocusRef,
}: DialogFrameProps) {
  const titleId = useId();
  const descriptionId = useId();
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);
  const dialogRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    previouslyFocusedRef.current = (document.activeElement as HTMLElement | null) || null;

    const focusTimer = window.setTimeout(() => {
      initialFocusRef?.current?.focus?.();
      if (dialogRef.current && !dialogRef.current.contains(document.activeElement)) {
        dialogRef.current.focus();
      }
    }, 0);

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        onCancel();
        return;
      }
      trapFocusOnTab(event, dialogRef.current);
    };

    document.addEventListener('keydown', onKeyDown, true);
    return () => {
      window.clearTimeout(focusTimer);
      document.removeEventListener('keydown', onKeyDown, true);
      previouslyFocusedRef.current?.focus?.();
    };
  }, [initialFocusRef, onCancel, open]);

  if (!open) return null;

  return (
    <div
      className="app-dialog-backdrop"
      onMouseDown={(event) => {
        if (event.target !== event.currentTarget) return;
        onCancel();
      }}
    >
      <div
        className="app-dialog"
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descriptionId : undefined}
        tabIndex={-1}
      >
        <h2 className="app-dialog-title" id={titleId}>
          {title}
        </h2>
        {description ? (
          <p className="app-dialog-desc" id={descriptionId}>
            {description}
          </p>
        ) : null}
        {children}
      </div>
    </div>
  );
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmText,
  confirmTone = 'primary',
  cancelText = '取消',
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  description?: string;
  confirmText: string;
  confirmTone?: 'primary' | 'danger';
  cancelText?: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const confirmRef = useRef<HTMLButtonElement | null>(null);
  const cancelRef = useRef<HTMLButtonElement | null>(null);

  return (
    <DialogFrame
      open={open}
      title={title}
      description={description}
      onCancel={onCancel}
      initialFocusRef={confirmTone === 'danger' ? cancelRef : confirmRef}
    >
      <div className="app-dialog-actions">
        <button type="button" ref={cancelRef} className="app-dialog-btn" onClick={onCancel}>
          {cancelText}
        </button>
        <button
          type="button"
          ref={confirmRef}
          className={`app-dialog-btn ${confirmTone}`}
          onClick={onConfirm}
        >
          {confirmText}
        </button>
      </div>
    </DialogFrame>
  );
}

export function PromptDialog({
  open,
  title,
  description,
  label = '会话名称',
  placeholder = '请输入…',
  confirmText = '保存',
  cancelText = '取消',
  defaultValue = '',
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  description?: string;
  label?: string;
  placeholder?: string;
  confirmText?: string;
  cancelText?: string;
  defaultValue?: string;
  onConfirm: (value: string) => void;
  onCancel: () => void;
}) {
  const [value, setValue] = useState(defaultValue);
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!open) return;
    setValue(defaultValue);
  }, [defaultValue, open]);

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    onConfirm(value);
  };

  return (
    <DialogFrame
      open={open}
      title={title}
      description={description}
      onCancel={onCancel}
      initialFocusRef={inputRef}
    >
      <form className="app-dialog-form" onSubmit={onSubmit}>
        <label htmlFor={inputId}>
          <span>{label}</span>
          <input
            id={inputId}
            ref={inputRef}
            value={value}
            placeholder={placeholder}
            onChange={(event) => setValue(event.target.value)}
          />
        </label>
        <div className="app-dialog-actions">
          <button type="button" className="app-dialog-btn" onClick={onCancel}>
            {cancelText}
          </button>
          <button type="submit" className="app-dialog-btn primary">
            {confirmText}
          </button>
        </div>
      </form>
    </DialogFrame>
  );
}
