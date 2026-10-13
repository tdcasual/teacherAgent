import TeacherAppLayout from './features/layout/TeacherAppLayout';
import { TeacherToolConfirmDialog } from './features/chat/TeacherToolConfirmDialog';
import { useTeacherAppController } from './useTeacherAppController';

export default function App() {
  const { layout, toolConfirm } = useTeacherAppController();
  return (
    <>
      <TeacherAppLayout {...layout} />
      <TeacherToolConfirmDialog {...toolConfirm} />
    </>
  );
}
