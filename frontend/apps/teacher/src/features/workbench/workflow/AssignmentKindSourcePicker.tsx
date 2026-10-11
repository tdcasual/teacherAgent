import type { AssignmentKind, ContentSource } from '../../../appTypes';
import type { AssignmentKindSourcePickerProps } from '../../../types/workflow';
import {
  ASSIGNMENT_KIND_OPTIONS,
  BANK_SOURCE_DISABLED_TITLE,
  CONTENT_SOURCE_OPTIONS,
} from '../workbenchUtils';

export default function AssignmentKindSourcePicker(props: AssignmentKindSourcePickerProps) {
  const { assignmentKind, contentSource, onAssignmentKindChange, onContentSourceChange } = props;
  const bankEnabled = assignmentKind === 'problem_set';

  return (
    <section
      data-testid="workflow-kind-source-picker"
      className="bg-surface border border-border rounded-[14px] shadow-sm p-[10px] grid gap-3"
    >
      <fieldset className="m-0 p-0 border-0 grid gap-2" data-testid="workflow-kind-picker">
        <legend className="text-[13px] font-semibold px-0">作业类型</legend>
        <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="作业类型">
          {ASSIGNMENT_KIND_OPTIONS.map((option) => (
            <label
              key={option.value}
              className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-2 min-h-11 cursor-pointer text-[13px] ${
                assignmentKind === option.value
                  ? 'border-[color:var(--color-accent)] bg-[color:var(--color-accent-soft)] text-[color:var(--color-accent)] font-semibold'
                  : 'border-border bg-white text-ink'
              }`}
            >
              <input
                type="radio"
                name="assignment-kind"
                value={option.value}
                checked={assignmentKind === option.value}
                data-testid={`workflow-kind-${option.value}`}
                onChange={() => onAssignmentKindChange(option.value as AssignmentKind)}
              />
              {option.label}
            </label>
          ))}
        </div>
      </fieldset>
      <fieldset className="m-0 p-0 border-0 grid gap-2" data-testid="workflow-source-picker">
        <legend className="text-[13px] font-semibold px-0">草稿来源</legend>
        <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="草稿来源">
          {CONTENT_SOURCE_OPTIONS.map((option) => {
            const isBank = option.value === 'bank';
            const disabled = isBank && !bankEnabled;
            return (
              <label
                key={option.value}
                title={disabled ? BANK_SOURCE_DISABLED_TITLE : undefined}
                className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-2 min-h-11 text-[13px] ${
                  disabled
                    ? 'opacity-60 cursor-not-allowed border-border bg-surface-soft text-muted'
                    : contentSource === option.value
                      ? 'border-[color:var(--color-accent)] bg-[color:var(--color-accent-soft)] text-[color:var(--color-accent)] font-semibold cursor-pointer'
                      : 'border-border bg-white text-ink cursor-pointer'
                }`}
              >
                <input
                  type="radio"
                  name="content-source"
                  value={option.value}
                  checked={contentSource === option.value}
                  disabled={disabled}
                  title={disabled ? BANK_SOURCE_DISABLED_TITLE : undefined}
                  data-testid={`workflow-source-${option.value}`}
                  onChange={() => {
                    if (disabled) return;
                    onContentSourceChange(option.value as ContentSource);
                  }}
                />
                {option.label}
              </label>
            );
          })}
        </div>
      </fieldset>
    </section>
  );
}
