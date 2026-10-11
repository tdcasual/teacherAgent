import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import AssignmentKindSourcePicker from './AssignmentKindSourcePicker';
import { BANK_SOURCE_DISABLED_TITLE } from '../workbenchUtils';

afterEach(() => {
  cleanup();
});

describe('AssignmentKindSourcePicker', () => {
  it('disables bank unless problem_set', () => {
    const onKind = vi.fn();
    const onSource = vi.fn();
    const { rerender } = render(
      <AssignmentKindSourcePicker
        assignmentKind="problem_set"
        contentSource="upload"
        onAssignmentKindChange={onKind}
        onContentSourceChange={onSource}
      />,
    );

    const bank = screen.getByTestId('workflow-source-bank') as HTMLInputElement;
    expect(bank.disabled).toBe(false);
    fireEvent.click(bank);
    expect(onSource).toHaveBeenCalledWith('bank');

    rerender(
      <AssignmentKindSourcePicker
        assignmentKind="scenario"
        contentSource="upload"
        onAssignmentKindChange={onKind}
        onContentSourceChange={onSource}
      />,
    );
    const disabledBank = screen.getByTestId('workflow-source-bank') as HTMLInputElement;
    expect(disabledBank.disabled).toBe(true);
    expect(disabledBank.title).toBe(BANK_SOURCE_DISABLED_TITLE);
    onSource.mockClear();
    fireEvent.click(disabledBank);
    expect(onSource).not.toHaveBeenCalled();
  });

  it('offers four kinds and three sources with problem_set default selected', () => {
    render(
      <AssignmentKindSourcePicker
        assignmentKind="problem_set"
        contentSource="upload"
        onAssignmentKindChange={vi.fn()}
        onContentSourceChange={vi.fn()}
      />,
    );
    expect((screen.getByTestId('workflow-kind-problem_set') as HTMLInputElement).checked).toBe(
      true,
    );
    expect(screen.getByTestId('workflow-kind-scenario')).toBeTruthy();
    expect(screen.getByTestId('workflow-kind-science_history')).toBeTruthy();
    expect(screen.getByTestId('workflow-kind-practical')).toBeTruthy();
    expect(screen.getByTestId('workflow-source-upload')).toBeTruthy();
    expect(screen.getByTestId('workflow-source-bank')).toBeTruthy();
    expect(screen.getByTestId('workflow-source-ai')).toBeTruthy();
  });
});
