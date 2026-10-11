import { useState, type FormEvent } from 'react';
import type { BankPickFormProps } from '../../../types/workflow';
import { clampQuestionCount } from '../workbenchUtils';
import LabeledField from './LabeledField';
import SourceIdentityFields from './SourceIdentityFields';

export default function BankPickForm(props: BankPickFormProps) {
  const { uploading, uploadError, uploadStatus, handleFromBank } = props;
  const [kp, setKp] = useState('');
  const [count, setCount] = useState(5);

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    void handleFromBank({ kp: kp.trim(), count: clampQuestionCount(count) });
  };

  return (
    <section
      id="workflow-bank-section"
      data-testid="workflow-bank-section"
      className="bg-surface border border-border rounded-[14px] shadow-sm p-[10px]"
    >
      <h3 className="m-0 mb-2">从题库选题</h3>
      <p className="m-0 mb-3 text-muted text-[13px]">
        按知识点从题库抽题生成草稿，审核后再发布。空库会提示题库不足。
      </p>
      <form className="grid gap-[10px]" onSubmit={onSubmit}>
        <SourceIdentityFields
          assignmentId={props.assignmentId}
          setAssignmentId={props.setAssignmentId}
          date={props.date}
          setDate={props.setDate}
          dueAt={props.dueAt}
          setDueAt={props.setDueAt}
          subjectId={props.subjectId}
          setSubjectId={props.setSubjectId}
          className={props.className}
          setClassName={props.setClassName}
          studentIds={props.studentIds}
          setStudentIds={props.setStudentIds}
          assignmentIdTestId="workflow-bank-assignment-id"
        />
        <LabeledField label="知识点（可选，逗号分隔）">
          <input
            data-testid="workflow-bank-kp"
            value={kp}
            onChange={(e) => setKp(e.target.value)}
            placeholder="例如：受力分析，牛顿定律"
          />
        </LabeledField>
        <LabeledField label="题量（1–20）">
          <input
            data-testid="workflow-bank-count"
            type="number"
            min={1}
            max={20}
            value={count}
            onChange={(e) => setCount(clampQuestionCount(e.target.value))}
          />
        </LabeledField>
        <button
          type="submit"
          data-testid="workflow-bank-submit"
          className="border-none rounded-xl py-[10px] px-[14px] bg-accent text-on-accent cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed min-h-11"
          disabled={uploading}
        >
          {uploading ? '选题中…' : '从题库生成草稿'}
        </button>
      </form>
      {uploadError ? (
        <div
          role="alert"
          className="mt-[10px] p-[10px_12px] rounded-xl text-[12px] whitespace-pre-wrap overflow-x-auto bg-danger-soft text-danger"
        >
          {uploadError}
        </div>
      ) : null}
      {uploadStatus ? (
        <pre className="mt-[10px] p-[10px_12px] rounded-xl text-[12px] whitespace-pre-wrap overflow-x-auto bg-success-soft text-success">
          {uploadStatus}
        </pre>
      ) : null}
    </section>
  );
}
