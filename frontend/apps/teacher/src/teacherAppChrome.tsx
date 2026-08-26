import { type MobileTabItem } from '../../shared/mobile/MobileTabBar'
import { MobileTabChatIcon, MobileTabSessionIcon, MobileTabWorkbenchIcon } from '../../shared/mobile/tabIcons'
import 'katex/dist/katex.min.css'

export const DEFAULT_API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
export const DESKTOP_BREAKPOINT = 900
export const WORKBENCH_DEFAULT_WIDTH = 320
export const WORKBENCH_MIN_WIDTH = 280
export const WORKBENCH_BASE_MAX_WIDTH = 620
export const WORKBENCH_MAX_WIDTH_RATIO = 0.42
export const WORKBENCH_HARD_MAX_WIDTH = 920
export const TEACHER_MOBILE_TAB_ITEMS: MobileTabItem[] = [
  { id: 'chat', label: '聊天', icon: <MobileTabChatIcon /> },
  { id: 'sessions', label: '会话', icon: <MobileTabSessionIcon /> },
  { id: 'workbench', label: '工作台', icon: <MobileTabWorkbenchIcon /> },
]
export const workbenchMaxWidthForViewport = (viewportWidth: number) => {
  const fluidMax = Math.round(viewportWidth * WORKBENCH_MAX_WIDTH_RATIO)
  return Math.min(WORKBENCH_HARD_MAX_WIDTH, Math.max(WORKBENCH_BASE_MAX_WIDTH, fluidMax))
}
