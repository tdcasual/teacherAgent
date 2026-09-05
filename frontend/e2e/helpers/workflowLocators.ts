import type { Locator, Page } from '@playwright/test'

export const workflowUploadSection = (page: Page): Locator => page.locator('#workflow-upload-section')

export const workflowUploadSubmitButton = (page: Page): Locator =>
  page.getByTestId('workflow-upload-submit')

export const workflowAssignmentScopeSelect = (page: Page): Locator =>
  workflowUploadSection(page).locator('label:has-text("范围") + select').first()

export const workflowStatusChip = (page: Page): Locator =>
  page.getByTestId('workflow-summary-status-chip').first()

export const assignmentDraftSection = (page: Page): Locator =>
  page.locator('#workflow-assignment-draft-section')

export const assignmentConfirmButton = (page: Page): Locator =>
  page.getByTestId('assignment-confirm-button')
