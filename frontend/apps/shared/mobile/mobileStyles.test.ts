import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const extractRuleBlock = (cssText: string, selector: string): string => {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const pattern = new RegExp(`${escapedSelector}\\s*\\{([\\s\\S]*?)\\}`, 'm');
  const match = cssText.match(pattern);
  return match ? match[1] : '';
};

describe('mobile shared style guardrails', () => {
  it('keeps mobile tab labels visually centered', () => {
    const cssPath = path.resolve(process.cwd(), 'apps/shared/mobile/mobile.css');
    const css = readFileSync(cssPath, 'utf8');
    const buttonBlock = extractRuleBlock(css, '.mobile-tabbar-button');
    const labelBlock = extractRuleBlock(css, '.mobile-tabbar-label');

    expect(buttonBlock).toContain('align-items: center;');
    expect(buttonBlock).toContain('justify-content: center;');
    expect(labelBlock).toContain('text-align: center;');
    expect(labelBlock).toContain('line-height: 1.2;');
  });

  it('keeps ghost buttons text vertically and horizontally centered', () => {
    const teacherCssPath = path.resolve(process.cwd(), 'apps/teacher/src/tailwind.css');
    const studentCssPath = path.resolve(process.cwd(), 'apps/student/src/tailwind.css');
    const teacherCss = readFileSync(teacherCssPath, 'utf8');
    const studentCss = readFileSync(studentCssPath, 'utf8');
    const teacherGhostBlock = extractRuleBlock(teacherCss, '.ghost');
    const studentGhostBlock = extractRuleBlock(studentCss, '.ghost');

    expect(teacherGhostBlock).toContain('display: inline-flex;');
    expect(teacherGhostBlock).toContain('align-items: center;');
    expect(teacherGhostBlock).toContain('justify-content: center;');
    expect(studentGhostBlock).toContain('display: inline-flex;');
    expect(studentGhostBlock).toContain('align-items: center;');
    expect(studentGhostBlock).toContain('justify-content: center;');
  });

  it('keeps tab icons at a stable touch-friendly visual size', () => {
    const cssPath = path.resolve(process.cwd(), 'apps/shared/mobile/mobile.css');
    const css = readFileSync(cssPath, 'utf8');
    const iconBlock = extractRuleBlock(css, '.mobile-tabbar-icon');
    const buttonBlock = extractRuleBlock(css, '.mobile-tabbar-button');

    expect(iconBlock).toContain('width: 16px;');
    expect(iconBlock).toContain('height: 16px;');
    expect(iconBlock).toContain('justify-content: center;');
    expect(buttonBlock).toContain(
      'color: color-mix(in oklab, var(--color-ink) 74%, white);',
    );
    expect(buttonBlock).toContain(
      'background: color-mix(in oklab, var(--mobile-sheet-surface) 88%, var(--color-surface-soft, white));',
    );
  });

  it('defines shared compact topbar density tokens and rules', () => {
    const cssPath = path.resolve(process.cwd(), 'apps/shared/mobile/mobile.css');
    const css = readFileSync(cssPath, 'utf8');
    const compactHeaderBlock = extractRuleBlock(
      css,
      ".app[data-mobile-shell-v2='1'] .mobile-topbar-compact",
    );
    const compactGhostBlock = extractRuleBlock(
      css,
      ".app[data-mobile-shell-v2='1'] .mobile-topbar-compact .ghost",
    );

    expect(css).toContain('--mobile-topbar-compact-height:');
    expect(css).toContain('--mobile-topbar-compact-btn-height:');
    expect(compactHeaderBlock).toContain('min-height: var(--mobile-topbar-compact-height);');
    expect(compactGhostBlock).toContain('min-height: var(--mobile-topbar-compact-btn-height);');
  });

  it('defines student today-home semantic tokens and shared mobile surface tokens', () => {
    const studentCssPath = path.resolve(process.cwd(), 'apps/student/src/tailwind.css');
    const mobileCssPath = path.resolve(process.cwd(), 'apps/shared/mobile/mobile.css');
    const studentCss = readFileSync(studentCssPath, 'utf8');
    const mobileCss = readFileSync(mobileCssPath, 'utf8');

    expect(studentCss).toContain('--color-app-bg:');
    expect(studentCss).toContain('--color-task-strip:');
    expect(studentCss).toContain('--color-note:');
    expect(studentCss).toContain('--color-progress:');
    expect(mobileCss).toContain('--mobile-tabbar-active-bg:');
    expect(mobileCss).toContain('--mobile-tabbar-active-fg:');
    expect(mobileCss).toContain('--mobile-sheet-surface:');
  });

  it('keeps student and teacher themes on the same restrained paper-and-ink palette', () => {
    const studentCssPath = path.resolve(process.cwd(), 'apps/student/src/tailwind.css');
    const teacherCssPath = path.resolve(process.cwd(), 'apps/teacher/src/tailwind.css');
    const studentCss = readFileSync(studentCssPath, 'utf8');
    const teacherCss = readFileSync(teacherCssPath, 'utf8');

    expect(studentCss).toContain('--color-app-bg: #FAFBFC;');
    expect(studentCss).toContain('--color-task-strip: #F7F9FF;');
    expect(studentCss).toContain('--color-accent: #0052CC;');
    expect(studentCss).toContain('--color-accent-soft: #DEEBFF;');

    expect(teacherCss).toContain('--color-app-bg: #FAFBFC;');
    expect(teacherCss).toContain('--color-rail: #F4F5F7;');
    expect(teacherCss).toContain('--color-accent: #0052CC;');
    expect(teacherCss).toContain('--color-success: #206A83;');
  });
});
