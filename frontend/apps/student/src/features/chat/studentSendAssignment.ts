export function isFreeAskSession(sessionId: string): boolean {
  const sid = String(sessionId || '').trim();
  return sid.startsWith('general_') || sid.startsWith('free-ask') || sid.startsWith('free_ask');
}

export function assignmentIdForStudentSend(input: {
  sessionId: string;
  selectedAssignmentId?: string;
  sessionAssignmentId?: string;
}): string | undefined {
  const sessionId = String(input.sessionId || '').trim();
  if (!sessionId || isFreeAskSession(sessionId)) return undefined;
  const stored = String(input.sessionAssignmentId || '').trim();
  if (stored) return stored;
  const selected = String(input.selectedAssignmentId || '').trim();
  return selected || undefined;
}
