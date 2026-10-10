import { useCallback, type KeyboardEvent } from 'react';

type UseTabListKeyboardArgs<T extends string> = {
  tabs: readonly T[];
  value: T;
  onChange: (next: T) => void;
};

export function useTabListKeyboard<T extends string>({
  tabs,
  value,
  onChange,
}: UseTabListKeyboardArgs<T>) {
  return useCallback(
    (event: KeyboardEvent<HTMLElement>) => {
      const current = tabs.indexOf(value);
      if (current < 0) return;
      let next = current;
      if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
        next = (current + 1) % tabs.length;
      } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
        next = (current - 1 + tabs.length) % tabs.length;
      } else if (event.key === 'Home') {
        next = 0;
      } else if (event.key === 'End') {
        next = tabs.length - 1;
      } else {
        return;
      }
      event.preventDefault();
      onChange(tabs[next]);
    },
    [onChange, tabs, value],
  );
}
