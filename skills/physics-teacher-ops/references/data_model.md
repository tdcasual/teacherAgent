# Data Model (Teacher Ops)

Use this as a shared reference when defining storage or exports. Treat exam responses as immutable facts; store derived analysis separately.

## Core Entities

- students: student_id, name, class_id, auth_token(optional)
- questions: question_id, stem_ref, answer_ref, max_score, chapter(optional), knowledge_points(optional), difficulty(optional), rubric(optional)
- papers: paper_id, title, question_order, question_scores
- exams: exam_id, paper_id, date, class_id, teacher_id(optional)
- responses: student_id, exam_id, question_id, question_no, sub_no(optional), raw_value, raw_answer(optional), score(optional), is_correct(optional)

## Analysis & Discussion

- exam_analysis: analysis_id, exam_id, version, status, auto_metrics, final_summary
- analysis_discussion: analysis_id, discussion_notes, overrides

## Lesson Assets

- lesson_plans: lesson_id, date, topic, target_kp, prereq_kp, plan_text
- lesson_assets: lesson_id, precheck_items, study_guide, homework_template

## Student Profiles (Derived)

- student_profiles: student_id, mastery_by_kp, recent_weak_kp, practice_history, summary

## Notes

- Keep question text and explanations as files if they are long; store file paths in *_ref fields.
- Keep knowledge point mappings flexible; allow null for uncategorized questions.
- Preserve original question numbering in question_no and sub_no for traceability.
