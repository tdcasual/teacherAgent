import type { Dispatch, ReactNode, RefObject } from 'react';
import type { VerifiedStudent } from '../../appTypes';
import type { StudentAction } from '../../hooks/useStudentState';
import StudentLayout from './StudentLayout';
import StudentTopbar from './StudentTopbar';

type Props = {
  appRef: RefObject<HTMLDivElement | null>;
  mobileShellV2Enabled: boolean;
  verifiedStudent: VerifiedStudent | null;
  sidebarOpen: boolean;
  homeOpen: boolean;
  assignmentHistoryOpen: boolean;
  submitAssignmentId: string;
  dispatch: Dispatch<StudentAction>;
  openTodayHome: () => void;
  startNewStudentSession: () => void;
  sidebar: ReactNode;
  learningContent: ReactNode;
  chatContent: ReactNode;
};

export default function StudentDesktopShell({
  appRef,
  mobileShellV2Enabled,
  verifiedStudent,
  sidebarOpen,
  homeOpen,
  assignmentHistoryOpen,
  submitAssignmentId,
  dispatch,
  openTodayHome,
  startNewStudentSession,
  sidebar,
  learningContent,
  chatContent,
}: Props) {
  return (
    <div
      className="app flex h-dvh flex-col bg-bg overflow-hidden"
      ref={appRef}
      data-mobile-shell-v2={mobileShellV2Enabled ? '1' : '0'}
    >
      <a
        href="#student-main"
        className="absolute left-[-999px] top-2 z-[1000] bg-surface text-ink px-3 py-2 rounded-md focus:left-2"
      >
        跳到主内容
      </a>
      <StudentTopbar
        verifiedStudent={verifiedStudent}
        sidebarOpen={sidebarOpen}
        homeActive={homeOpen}
        dispatch={dispatch}
        openTodayHome={openTodayHome}
        startNewStudentSession={startNewStudentSession}
      />
      <StudentLayout
        sidebarOpen={sidebarOpen}
        sidebar={sidebar}
        chat={
          homeOpen || assignmentHistoryOpen || Boolean(submitAssignmentId)
            ? learningContent
            : chatContent
        }
      />
    </div>
  );
}
