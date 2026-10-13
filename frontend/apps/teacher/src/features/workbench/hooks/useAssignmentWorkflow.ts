import { useDraftMutations } from './useDraftMutations';
import { useAssignmentProgressActions } from './useAssignmentProgressActions';
import { useConfirmPublish } from './useConfirmPublish';
import { useWorkflowIndicatorEffects } from './useWorkflowIndicatorEffects';
import { useUploadAssignment } from './useUploadAssignment';
import { useBankAndAiDraft } from './useBankAndAiDraft';
import type {
  UseAssignmentWorkflowParams,
  UseAssignmentWorkflowReturn,
} from '../../../types/workflow';

export type { UseAssignmentWorkflowParams, UseAssignmentWorkflowReturn };

export function useAssignmentWorkflow(
  params: UseAssignmentWorkflowParams,
): UseAssignmentWorkflowReturn {
  const draft = useDraftMutations(params);
  const progress = useAssignmentProgressActions(params);
  // confirm needs saveDraft / fetchAssignmentProgress from the prior hooks
  const confirm = useConfirmPublish({
    ...params,
    saveDraft: draft.saveDraft,
    fetchAssignmentProgress: progress.fetchAssignmentProgress,
  });
  const effects = useWorkflowIndicatorEffects(params);
  const upload = useUploadAssignment(params);
  const bank = useBankAndAiDraft(params);
  return { ...draft, ...progress, ...confirm, ...effects, ...upload, ...bank };
}
