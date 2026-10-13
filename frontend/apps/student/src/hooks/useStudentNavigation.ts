import { useCallback, useEffect, useMemo, useState, type Dispatch } from 'react';
import { readFeatureFlag } from '../../../shared/featureFlags';
import type { StudentTodayHomeViewModel, VerifiedStudent } from '../appTypes';
import {
  isStudentMobileTab,
  studentMobilePanelsFromTab,
  studentMobileTabFromPanels,
  type StudentMobileTab,
} from '../features/layout/mobileShellState';
import { todayDate, type StudentAction } from './useStudentState';

const DESKTOP_BREAKPOINT = 900;

type UseStudentNavigationParams = {
  dispatch: Dispatch<StudentAction>;
  verifiedStudent: VerifiedStudent | null;
  sidebarOpen: boolean;
  verifyOpen: boolean;
  setActiveSession: (sessionId: string) => void;
  todayHomeViewModel: StudentTodayHomeViewModel;
  startNewStudentSession: () => void;
};

export function useStudentNavigation({
  dispatch,
  verifiedStudent,
  sidebarOpen,
  verifyOpen,
  setActiveSession,
  todayHomeViewModel,
  startNewStudentSession,
}: UseStudentNavigationParams) {
  const [viewportWidth, setViewportWidth] = useState(() =>
    typeof window !== 'undefined' ? window.innerWidth : 1280,
  );
  const [homeOpen, setHomeOpen] = useState(true);
  const [assignmentHistoryOpen, setAssignmentHistoryOpen] = useState(false);
  const [submitAssignmentId, setSubmitAssignmentId] = useState('');
  const [mobileTab, setMobileTab] = useState<StudentMobileTab>('learning');
  const [mobileSessionListOpen, setMobileSessionListOpen] = useState(false);
  const isMobileLayout = viewportWidth <= DESKTOP_BREAKPOINT;
  const mobileShellV2Enabled = useMemo(() => {
    const source: Record<string, string | undefined> = {
      mobileShellV2: import.meta.env.VITE_MOBILE_SHELL_V2_STUDENT,
    };
    if (typeof window !== 'undefined') {
      try {
        const localOverride = window.localStorage.getItem('studentMobileShellV2');
        if (localOverride != null) source.mobileShellV2 = localOverride;
      } catch {
        // ignore localStorage read failures
      }
    }
    return readFeatureFlag('mobileShellV2', true, source);
  }, []);
  const studentUseMobileShellV2 = mobileShellV2Enabled && isMobileLayout;

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const onResize = () => setViewportWidth(window.innerWidth);
    onResize();
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  useEffect(() => {
    if (!studentUseMobileShellV2) return;
    const nextTab = studentMobileTabFromPanels({
      sessionListOpen: mobileSessionListOpen,
      verifyOpen,
      homeOpen,
    });
    if (mobileTab !== nextTab) setMobileTab(nextTab);
  }, [studentUseMobileShellV2, verifyOpen, homeOpen, mobileSessionListOpen, mobileTab]);

  useEffect(() => {
    if (verifiedStudent?.student_id) return;
    setHomeOpen(true);
  }, [verifiedStudent?.student_id]);

  const handleMobileTabChange = useCallback(
    (tabId: string) => {
      if (!isStudentMobileTab(tabId)) return;
      setMobileTab(tabId);
      if (!studentUseMobileShellV2) return;
      const nextPanels = studentMobilePanelsFromTab(tabId);
      setHomeOpen(nextPanels.homeOpen);
      setMobileSessionListOpen(nextPanels.sessionListOpen);
      if (verifyOpen !== nextPanels.verifyOpen) {
        dispatch({ type: 'SET', field: 'verifyOpen', value: nextPanels.verifyOpen });
      }
      if (sidebarOpen) {
        dispatch({ type: 'SET', field: 'sidebarOpen', value: false });
      }
    },
    [studentUseMobileShellV2, sidebarOpen, verifyOpen, dispatch],
  );

  const openTodayHome = useCallback(() => {
    setHomeOpen(true);
    setSubmitAssignmentId('');
    setAssignmentHistoryOpen(false);
    if (!studentUseMobileShellV2) return;
    setMobileTab('learning');
    setMobileSessionListOpen(false);
    if (sidebarOpen) {
      dispatch({ type: 'SET', field: 'sidebarOpen', value: false });
    }
  }, [dispatch, sidebarOpen, studentUseMobileShellV2]);

  const openExecutionState = useCallback(() => {
    setHomeOpen(false);
    if (!studentUseMobileShellV2) return;
    setMobileTab('chat');
    setMobileSessionListOpen(false);
    if (sidebarOpen) {
      dispatch({ type: 'SET', field: 'sidebarOpen', value: false });
    }
  }, [dispatch, sidebarOpen, studentUseMobileShellV2]);

  const handleOpenAssignment = useCallback(
    (assignmentId: string) => {
      const aid = assignmentId.trim();
      if (!aid) return;
      dispatch({ type: 'SET', field: 'selectedAssignmentId', value: aid });
      setSubmitAssignmentId('');
      setActiveSession(aid);
      openExecutionState();
    },
    [dispatch, openExecutionState, setActiveSession],
  );

  const handleOpenSubmit = useCallback(
    (assignmentId: string) => {
      const aid = assignmentId.trim();
      if (!aid) return;
      dispatch({ type: 'SET', field: 'selectedAssignmentId', value: aid });
      setSubmitAssignmentId(aid);
      if (!studentUseMobileShellV2) return;
      setHomeOpen(true);
      setMobileTab('learning');
      setMobileSessionListOpen(false);
      if (sidebarOpen) {
        dispatch({ type: 'SET', field: 'sidebarOpen', value: false });
      }
    },
    [dispatch, sidebarOpen, studentUseMobileShellV2],
  );

  const handlePrimaryHomeAction = useCallback(() => {
    if (!verifiedStudent) {
      dispatch({ type: 'SET', field: 'verifyOpen', value: true });
      return;
    }
    if (
      todayHomeViewModel.status === 'empty' ||
      todayHomeViewModel.status === 'generating' ||
      todayHomeViewModel.status === 'pending_generation'
    )
      return;
    if (todayHomeViewModel.status === 'submitted') {
      setAssignmentHistoryOpen(true);
      return;
    }
    const firstId = todayHomeViewModel.items[0]?.assignment_id || '';
    if (firstId) {
      handleOpenAssignment(firstId);
      return;
    }
    openExecutionState();
  }, [
    dispatch,
    handleOpenAssignment,
    openExecutionState,
    verifiedStudent,
    todayHomeViewModel.items,
    todayHomeViewModel.status,
  ]);

  const handleOpenAssignmentHistory = useCallback(() => {
    setSubmitAssignmentId('');
    setAssignmentHistoryOpen(true);
    setHomeOpen(true);
    if (!studentUseMobileShellV2) return;
    setMobileTab('learning');
    setMobileSessionListOpen(false);
    if (sidebarOpen) {
      dispatch({ type: 'SET', field: 'sidebarOpen', value: false });
    }
  }, [dispatch, sidebarOpen, studentUseMobileShellV2]);

  const handleOpenHistory = useCallback(() => {
    setHomeOpen(false);
    if (studentUseMobileShellV2) {
      setMobileSessionListOpen(true);
      setMobileTab('sessions');
      if (sidebarOpen) {
        dispatch({ type: 'SET', field: 'sidebarOpen', value: false });
      }
      return;
    }
    dispatch({ type: 'SET', field: 'sidebarOpen', value: true });
  }, [dispatch, sidebarOpen, studentUseMobileShellV2]);

  const handleOpenFreeChat = useCallback(() => {
    dispatch({ type: 'SET', field: 'selectedAssignmentId', value: '' });
    setSubmitAssignmentId('');
    setAssignmentHistoryOpen(false);
    setActiveSession(`general_${todayDate()}`);
    openExecutionState();
  }, [dispatch, openExecutionState, setActiveSession]);

  const handleStartNewStudentSession = useCallback(() => {
    openExecutionState();
    startNewStudentSession();
  }, [openExecutionState, startNewStudentSession]);

  return {
    mobileShellV2Enabled,
    studentUseMobileShellV2,
    homeOpen,
    setHomeOpen,
    assignmentHistoryOpen,
    setAssignmentHistoryOpen,
    submitAssignmentId,
    setSubmitAssignmentId,
    mobileTab,
    setMobileTab,
    mobileSessionListOpen,
    setMobileSessionListOpen,
    handleMobileTabChange,
    openTodayHome,
    handleOpenAssignment,
    handleOpenSubmit,
    handlePrimaryHomeAction,
    handleOpenAssignmentHistory,
    handleOpenHistory,
    handleOpenFreeChat,
    handleStartNewStudentSession,
  };
}

export type StudentNavigation = ReturnType<typeof useStudentNavigation>;
