import type { Dispatch, SetStateAction } from 'react'
import type { WorkbenchTab } from '../../appTypes'
import type { MemoryTabProps } from './tabs/MemoryTab'
import type { SkillsTabProps } from './tabs/SkillsTab'
import type { WorkflowTabProps } from './tabs/WorkflowTab'

export type TeacherWorkbenchChromeProps = {
  skillsOpen: boolean
  setSkillsOpen: Dispatch<SetStateAction<boolean>>
  workbenchTab: WorkbenchTab
  setWorkbenchTab: Dispatch<SetStateAction<WorkbenchTab>>
  fetchSkills: SkillsTabProps['fetchSkills']
  refreshMemoryProposals: () => Promise<void>
  refreshMemoryInsights: () => Promise<void>
  refreshStudentMemoryProposals: () => Promise<void>
  refreshStudentMemoryInsights: () => Promise<void>
  refreshWorkflowWorkbench: () => void
  skillsLoading: boolean
  proposalLoading: boolean
  studentProposalLoading: boolean
  progressLoading: boolean
  uploading: boolean
  examUploading: boolean
}

export type TeacherWorkbenchViewModel = TeacherWorkbenchChromeProps &
  SkillsTabProps &
  MemoryTabProps &
  WorkflowTabProps

type BuildTeacherWorkbenchViewModelParams<
  TWorkbench extends object,
  TRest extends object,
> = {
  workbench: TWorkbench
} & TRest

export function buildTeacherWorkbenchViewModel<
  TWorkbench extends object,
  TRest extends object,
>(
  params: BuildTeacherWorkbenchViewModelParams<TWorkbench, TRest>,
): TWorkbench & TRest {
  const { workbench, ...rest } = params
  return {
    ...workbench,
    ...rest,
  } as TWorkbench & TRest
}
