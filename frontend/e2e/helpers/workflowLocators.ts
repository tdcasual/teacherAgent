import type { Locator, Page } from '@playwright/test'

export const workflowUploadSection = (page: Page): Locator => page.locator('#workflow-upload-section')

export const workflowUploadSubmitButton = (page: Page): Locator =>
  workflowUploadSection(page).locator('button[type="submit"]')

export const workflowAssignmentScopeSelect = (page: Page): Locator =>
  workflowUploadSection(page).locator('label:has-text("范围") + select').first()

export const workflowUploadModeButton = (page: Page, mode: '作业' | '考试'): Locator =>
  workflowUploadSection(page).getByRole('button', { name: mode, exact: true }).first()

export const workflowStatusChip = (page: Page): Locator =>
  page.getByText('当前流程状态', { exact: true }).locator('xpath=following-sibling::span[1]')

export const assignmentDraftSection = (page: Page): Locator =>
  page.locator('#workflow-assignment-draft-section')

export const assignmentConfirmButton = (page: Page): Locator =>
  assignmentDraftSection(page)
    .getByRole('button', { name: /保存草稿|保存中…/ })
    .first()
    .locator('xpath=following-sibling::button[1]')
