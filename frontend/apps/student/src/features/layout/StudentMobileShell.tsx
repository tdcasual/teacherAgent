import type { Dispatch, ReactNode, RefObject } from 'react';
import { MobileTabBar, type MobileTabItem } from '../../../../shared/mobile/MobileTabBar';
import {
  MobileTabChatIcon,
  MobileTabLearningIcon,
  MobileTabSessionIcon,
} from '../../../../shared/mobile/tabIcons';
import type { VerifiedStudent } from '../../appTypes';
import type { StudentAction } from '../../hooks/useStudentState';
import type { StudentMobileTab } from './mobileShellState';
import StudentTopbar from './StudentTopbar';

const MOBILE_TAB_ITEMS: MobileTabItem[] = [
  { id: 'chat', label: '聊天', icon: <MobileTabChatIcon /> },
  { id: 'sessions', label: '会话', icon: <MobileTabSessionIcon /> },
  { id: 'learning', label: '学习', icon: <MobileTabLearningIcon /> },
];

type Props = {
  appRef: RefObject<HTMLDivElement | null>;
  mobileShellV2Enabled: boolean;
  verifiedStudent: VerifiedStudent | null;
  sidebarOpen: boolean;
  homeOpen: boolean;
  dispatch: Dispatch<StudentAction>;
  openTodayHome: () => void;
  startNewStudentSession: () => void;
  mobileTab: StudentMobileTab;
  onMobileTabChange: (tabId: string) => void;
  mobileLearningContent: ReactNode;
  mobileSessionsContent: ReactNode;
  chatContent: ReactNode;
  sessionDialogs: ReactNode;
};

export default function StudentMobileShell({
  appRef,
  mobileShellV2Enabled,
  verifiedStudent,
  sidebarOpen,
  homeOpen,
  dispatch,
  openTodayHome,
  startNewStudentSession,
  mobileTab,
  onMobileTabChange,
  mobileLearningContent,
  mobileSessionsContent,
  chatContent,
  sessionDialogs,
}: Props) {
  return (
    <div
      className="app flex h-dvh flex-col bg-bg overflow-hidden student-mobile-shell-v2"
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
        compactMobile
        dispatch={dispatch}
        openTodayHome={openTodayHome}
        startNewStudentSession={startNewStudentSession}
      />
      <div className="student-mobile-shell-main" id="student-main">
        {mobileTab === 'learning'
          ? mobileLearningContent
          : mobileTab === 'sessions'
            ? mobileSessionsContent
            : chatContent}
        {sessionDialogs}
      </div>
      <MobileTabBar
        items={MOBILE_TAB_ITEMS}
        activeId={mobileTab}
        onChange={onMobileTabChange}
        ariaLabel="学生端移动导航"
      />
    </div>
  );
}
