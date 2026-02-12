export type TeacherWorkbenchViewModel = Record<string, any>

type BuildTeacherWorkbenchViewModelParams = {
  workbench: Record<string, any>
} & Record<string, any>

export function buildTeacherWorkbenchViewModel(
  params: BuildTeacherWorkbenchViewModelParams,
): TeacherWorkbenchViewModel {
  const { workbench, ...rest } = params
  return {
    ...workbench,
    ...rest,
  }
}
