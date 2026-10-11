import { useState, type FormEvent } from 'react';
import type { AiDraftFormProps } from '../../../types/workflow';
import { clampQuestionCount } from '../workbenchUtils';
import LabeledField from './LabeledField';
import SourceIdentityFields from './SourceIdentityFields';

export default function AiDraftForm(props: AiDraftFormProps) {
  const { assignmentKind, uploading, uploadError, uploadStatus, handleGenerate } = props;
  const isProblemSet = assignmentKind === 'problem_set';
  const [kp, setKp] = useState('');
  const [perKp, setPerKp] = useState(5);
  const [topic, setTopic] = useState('');
  const [gradeLevel, setGradeLevel] = useState('');
  const [seed, setSeed] = useState('');

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    void handleGenerate({
      kp: kp.trim(),
      perKp: clampQuestionCount(perKp),
      topic: topic.trim(),
      gradeLevel: gradeLevel.trim(),
      seed: seed.trim(),
    });
  };

  return (
    <section
      id="workflow-ai-section"
      data-testid="workflow-ai-section"
      className="bg-surface border border-border rounded-[14px] shadow-sm p-[10px]"
    >
      <h3 className="m-0 mb-2">AI 起草草稿</h3>
      <p className="m-0 mb-3 text-muted text-[13px]">
        {isProblemSet
          ? '按知识点生成做题草稿，审核后再发布。'
          : '填写主题与年级，模型起草说明；可选种子不是完整 brief。'}
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
          assignmentIdTestId="workflow-ai-assignment-id"
        />
        {isProblemSet ? (
          <>
            <LabeledField label="知识点（可选，逗号分隔）">
              <input
                data-testid="workflow-ai-kp"
                value={kp}
                onChange={(e) => setKp(e.target.value)}
                placeholder="例如：电场强度"
              />
            </LabeledField>
            <LabeledField label="每知识点题量（1–20）">
              <input
                data-testid="workflow-ai-per-kp"
                type="number"
                min={1}
                max={20}
                value={perKp}
                onChange={(e) => setPerKp(clampQuestionCount(e.target.value))}
              />
            </LabeledField>
          </>
        ) : (
          <>
            <LabeledField label="主题">
              <input
                data-testid="workflow-ai-topic"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="例如：测量小灯泡伏安特性"
              />
            </LabeledField>
            <LabeledField label="年级">
              <input
                data-testid="workflow-ai-grade"
                value={gradeLevel}
                onChange={(e) => setGradeLevel(e.target.value)}
                placeholder="例如：高二"
              />
            </LabeledField>
            <LabeledField label="种子说明（可选）">
              <textarea
                data-testid="workflow-ai-seed"
                value={seed}
                onChange={(e) => setSeed(e.target.value)}
                rows={3}
                placeholder="可选，给模型一点情景线索，不必写完整 brief"
              />
            </LabeledField>
          </>
        )}
        <button
          type="submit"
          data-testid="workflow-ai-submit"
          className="border-none rounded-xl py-[10px] px-[14px] bg-accent text-on-accent cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed min-h-11"
          disabled={uploading}
        >
          {uploading ? '起草中…' : '生成草稿'}
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
