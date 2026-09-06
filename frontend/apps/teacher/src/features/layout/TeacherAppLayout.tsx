import {
  lazy,
  Suspense,
  useEffect,
  useState,
  type ComponentProps,
  type CSSProperties,
  type MutableRefObject,
  type ReactNode,
} from 'react';
import { Group, Panel, Separator } from 'react-resizable-panels';
import type { PanelImperativeHandle } from 'react-resizable-panels';
import TeacherTopbar from './TeacherTopbar';
import TeacherChatMainContent from '../chat/TeacherChatMainContent';
import TeacherSessionRail from '../chat/TeacherSessionRail';
import SessionSidebar from '../chat/SessionSidebar';
import type { TeacherWorkbenchViewModel } from '../workbench/teacherWorkbenchViewModel';
import { ConfirmDialog, PromptDialog } from '../../../../shared/dialog';
import { BottomSheet } from '../../../../shared/mobile/BottomSheet';
import { MobileTabBar } from '../../../../shared/mobile/MobileTabBar';
import { formatSessionUpdatedLabel } from '../../utils/time';
import { TEACHER_MOBILE_TAB_ITEMS, WORKBENCH_MIN_WIDTH } from '../../teacherAppChrome';
import type { TeacherMobileTab } from './mobileShellState';
import { TEACHER_AUTH_EVENT, readTeacherAuthRole } from '../auth/teacherAuth';

// Keep workbench and settings out of the teacher shell chunk.
const TeacherWorkbench = lazy(() => import('../workbench/TeacherWorkbench'));
const TeacherSettingsPanel = lazy(() => import('../settings/TeacherSettingsPanel'));
const AdminSchoolPanel = lazy(() => import('../admin/AdminSchoolPanel'));

const workbenchFallback = <div className="h-full w-full min-h-0 bg-surface" aria-busy="true" />;

function SuspendedTeacherWorkbench({ viewModel }: { viewModel: TeacherWorkbenchViewModel }) {
  return (
    <Suspense fallback={workbenchFallback}>
      <TeacherWorkbench viewModel={viewModel} />
    </Suspense>
  );
}

type SessionSidebarSharedProps = Omit<
  ComponentProps<typeof SessionSidebar>,
  'open' | 'mobilePresentation' | 'onSelectSession' | 'formatSessionUpdatedLabel'
>;

type TeacherChatProps = Omit<ComponentProps<typeof TeacherChatMainContent>, 'taskStrip'>;

export type TeacherAppLayoutProps = {
  appRef: MutableRefObject<HTMLDivElement | null>;
  topbarRef: MutableRefObject<HTMLElement | null>;
  workbenchPanelRef: MutableRefObject<PanelImperativeHandle | null>;
  topbarHeight: number;
  teacherUseMobileShellV2: boolean;
  mobileShellV2Enabled: boolean;
  sessionSidebarOpen: boolean;
  skillsOpen: boolean;
  isMobileLayout: boolean;
  isWorkbenchResizing: boolean;
  workbenchMaxWidth: number;
  initialWorkbenchWidth: number;
  mobileTab: TeacherMobileTab;
  setMobileTab: (tab: TeacherMobileTab) => void;
  settingsOpen: boolean;
  apiBase: string;
  onApiBaseChange: (value: string) => void;
  onCloseSettings: () => void;
  onToggleSessionSidebar: () => void;
  onOpenModelSettingsPanel: () => void;
  onToggleSkillsWorkbench: () => void;
  onToggleSettingsPanel: () => void;
  startWorkbenchResize: () => void;
  onWorkbenchResizeReset: () => void;
  onMobileTabChange: (tabId: string) => void;
  onSelectSessionFromSheet: (sessionId: string) => void;
  setSessionSidebarOpen: (value: boolean) => void;
  setSkillsOpen: (value: boolean) => void;
  setActiveSessionId: (value: string) => void;
  setSessionCursor: (value: number) => void;
  setSessionHasMore: (value: boolean) => void;
  setSessionError: (value: string) => void;
  setOpenSessionMenuId: (value: string) => void;
  closeSessionSidebarOnMobile: () => void;
  taskStrip: ReactNode;
  workbenchViewModel: TeacherWorkbenchViewModel;
  sessionSidebar: SessionSidebarSharedProps;
  chat: TeacherChatProps;
  renameDialogSessionId: string | null;
  archiveDialogSessionId: string | null;
  archiveDialogActionLabel: string;
  archiveDialogIsArchived: boolean;
  onCancelRenameDialog: () => void;
  onConfirmRenameDialog: (value: string) => void;
  onCancelArchiveDialog: () => void;
  onConfirmArchiveDialog: () => void;
};

export default function TeacherAppLayout({
  appRef,
  topbarRef,
  workbenchPanelRef,
  topbarHeight,
  teacherUseMobileShellV2,
  mobileShellV2Enabled,
  sessionSidebarOpen,
  skillsOpen,
  isMobileLayout,
  isWorkbenchResizing,
  workbenchMaxWidth,
  initialWorkbenchWidth,
  mobileTab,
  setMobileTab,
  settingsOpen,
  apiBase,
  onApiBaseChange,
  onCloseSettings,
  onToggleSessionSidebar,
  onOpenModelSettingsPanel,
  onToggleSkillsWorkbench,
  onToggleSettingsPanel,
  startWorkbenchResize,
  onWorkbenchResizeReset,
  onMobileTabChange,
  onSelectSessionFromSheet,
  setSessionSidebarOpen,
  setSkillsOpen,
  setActiveSessionId,
  setSessionCursor,
  setSessionHasMore,
  setSessionError,
  setOpenSessionMenuId,
  closeSessionSidebarOnMobile,
  taskStrip,
  workbenchViewModel,
  sessionSidebar,
  chat,
  renameDialogSessionId,
  archiveDialogSessionId,
  archiveDialogActionLabel,
  archiveDialogIsArchived,
  onCancelRenameDialog,
  onConfirmRenameDialog,
  onCancelArchiveDialog,
  onConfirmArchiveDialog,
}: TeacherAppLayoutProps) {
  const [isAdmin, setIsAdmin] = useState(() => readTeacherAuthRole() === 'admin');
  useEffect(() => {
    const sync = () => setIsAdmin(readTeacherAuthRole() === 'admin');
    sync();
    window.addEventListener('storage', sync);
    window.addEventListener(TEACHER_AUTH_EVENT, sync as EventListener);
    return () => {
      window.removeEventListener('storage', sync);
      window.removeEventListener(TEACHER_AUTH_EVENT, sync as EventListener);
    };
  }, []);
  const appStyle: CSSProperties & Record<'--teacher-topbar-height', string> = {
    '--teacher-topbar-height': `${topbarHeight}px`,
    overscrollBehavior: 'none',
  };
  const closeMobileSheet = () => setMobileTab('chat');

  return (
    <div
      ref={appRef}
      className={`app teacher h-dvh flex flex-col bg-bg overflow-hidden ${teacherUseMobileShellV2 ? 'teacher-mobile-shell-v2' : ''}`.trim()}
      style={appStyle}
      data-mobile-shell-v2={mobileShellV2Enabled ? '1' : '0'}
    >
      <TeacherTopbar
        topbarRef={topbarRef}
        sessionSidebarOpen={sessionSidebarOpen}
        skillsOpen={skillsOpen}
        compactMobile={teacherUseMobileShellV2}
        onToggleSessionSidebar={onToggleSessionSidebar}
        onOpenModelSettingsPanel={onOpenModelSettingsPanel}
        onToggleSkillsWorkbench={onToggleSkillsWorkbench}
        onToggleSettingsPanel={onToggleSettingsPanel}
      />
      {settingsOpen ? (
        <Suspense fallback={null}>
          <TeacherSettingsPanel
            open={settingsOpen}
            onClose={onCloseSettings}
            apiBase={apiBase}
            onApiBaseChange={onApiBaseChange}
          />
        </Suspense>
      ) : null}
      {isAdmin ? (
        <div className="teacher-layout flex-1 min-h-0 min-w-0 overflow-hidden bg-surface">
          <Suspense fallback={workbenchFallback}>
            <AdminSchoolPanel />
          </Suspense>
        </div>
      ) : (
        <div
          className={`teacher-layout flex-1 min-h-0 grid relative bg-surface overflow-hidden ${
            teacherUseMobileShellV2
              ? 'grid-cols-[minmax(0,1fr)]'
              : sessionSidebarOpen
                ? 'grid-cols-[300px_minmax(0,1fr)] max-[900px]:grid-cols-[minmax(0,1fr)]'
                : 'grid-cols-[0_minmax(0,1fr)]'
          }`}
          style={{ overscrollBehavior: 'none' }}
        >
          {teacherUseMobileShellV2 ? null : (
            <TeacherSessionRail
              sessionSidebarOpen={sessionSidebarOpen}
              skillsOpen={skillsOpen}
              setSessionSidebarOpen={setSessionSidebarOpen}
              setSkillsOpen={setSkillsOpen}
              setActiveSessionId={setActiveSessionId}
              setSessionCursor={setSessionCursor}
              setSessionHasMore={setSessionHasMore}
              setSessionError={setSessionError}
              setOpenSessionMenuId={setOpenSessionMenuId}
              closeSessionSidebarOnMobile={closeSessionSidebarOnMobile}
              {...sessionSidebar}
              formatSessionUpdatedLabel={formatSessionUpdatedLabel}
            />
          )}
          <div className="min-w-0 min-h-0 flex overflow-hidden">
            <Group
              orientation="horizontal"
              disabled={isMobileLayout}
              className={`w-full h-full min-w-0 min-h-0 ${isWorkbenchResizing ? 'dragging' : ''}`}
            >
              <Panel
                className="min-w-0 min-h-0 overflow-hidden flex"
                minSize={isMobileLayout ? 0 : 360}
              >
                <TeacherChatMainContent {...chat} taskStrip={taskStrip} />
              </Panel>
              {teacherUseMobileShellV2 ? null : (
                <>
                  <Separator
                    className={`group w-2 cursor-col-resize flex items-center justify-center bg-transparent transition-[background] duration-150 ease-in-out shrink-0 hover:bg-[color:color-mix(in_oklab,var(--color-accent-soft)_72%,var(--color-surface))] ${isWorkbenchResizing ? 'bg-[color:color-mix(in_oklab,var(--color-accent-soft)_72%,var(--color-surface))]' : ''} ${!skillsOpen ? 'cursor-default pointer-events-none' : ''}`}
                    onPointerDown={startWorkbenchResize}
                    onDoubleClick={onWorkbenchResizeReset}
                  >
                    <span
                      className={`w-[3px] h-7 rounded-sm transition-[background] duration-150 ease-in-out ${isWorkbenchResizing ? 'bg-accent' : 'bg-border-strong group-hover:bg-accent'}`}
                    />
                  </Separator>
                  <Panel
                    panelRef={workbenchPanelRef}
                    className="min-w-0 min-h-0 overflow-hidden flex"
                    minSize={WORKBENCH_MIN_WIDTH}
                    maxSize={workbenchMaxWidth}
                    defaultSize={initialWorkbenchWidth}
                    collapsible
                    collapsedSize={0}
                    onResize={(panelSize) => {
                      if (isMobileLayout) return;
                      const width = Math.round(panelSize.inPixels || 0);
                      if (!Number.isFinite(width) || width <= 0) return;
                      const clamped = Math.min(
                        workbenchMaxWidth,
                        Math.max(WORKBENCH_MIN_WIDTH, width),
                      );
                      try {
                        window.localStorage.setItem('teacherWorkbenchWidth', String(clamped));
                      } catch {
                        // ignore
                      }
                    }}
                  >
                    <SuspendedTeacherWorkbench viewModel={workbenchViewModel} />
                  </Panel>
                </>
              )}
            </Group>
          </div>
        </div>
      )}
      {isAdmin ? null : (
        <>
          <BottomSheet
            open={teacherUseMobileShellV2 && mobileTab === 'sessions'}
            onClose={closeMobileSheet}
            title="历史会话"
          >
            <SessionSidebar
              mobilePresentation="sheet"
              open
              {...sessionSidebar}
              onSelectSession={onSelectSessionFromSheet}
              formatSessionUpdatedLabel={formatSessionUpdatedLabel}
            />
          </BottomSheet>
          <BottomSheet
            open={teacherUseMobileShellV2 && mobileTab === 'workbench'}
            onClose={closeMobileSheet}
            title="工作台"
          >
            <SuspendedTeacherWorkbench viewModel={workbenchViewModel} />
          </BottomSheet>
          {teacherUseMobileShellV2 ? (
            <MobileTabBar
              items={TEACHER_MOBILE_TAB_ITEMS}
              activeId={mobileTab}
              onChange={onMobileTabChange}
              ariaLabel="教师端移动导航"
            />
          ) : null}
        </>
      )}
      <PromptDialog
        open={Boolean(renameDialogSessionId)}
        title="重命名会话"
        description="可留空以删除自定义名称。"
        label="会话名称"
        placeholder="输入会话名称"
        defaultValue={
          renameDialogSessionId ? sessionSidebar.getSessionTitle(renameDialogSessionId) : ''
        }
        confirmText="保存"
        onCancel={onCancelRenameDialog}
        onConfirm={onConfirmRenameDialog}
      />
      <ConfirmDialog
        open={Boolean(archiveDialogSessionId)}
        title={`确认${archiveDialogActionLabel}会话？`}
        description={
          archiveDialogSessionId
            ? `会话：${sessionSidebar.getSessionTitle(archiveDialogSessionId)}`
            : undefined
        }
        confirmText={archiveDialogActionLabel}
        confirmTone={archiveDialogIsArchived ? 'primary' : 'danger'}
        cancelText="取消"
        onCancel={onCancelArchiveDialog}
        onConfirm={onConfirmArchiveDialog}
      />
    </div>
  );
}
