import { readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const extractRuleBlock = (cssText: string, selector: string): string => {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const pattern = new RegExp(`${escapedSelector}\\s*\\{([\\s\\S]*?)\\}`, 'm');
  const match = cssText.match(pattern);
  return match ? match[1] : '';
};

const frontendFile = (...segments: string[]) => path.resolve(process.cwd(), ...segments);

const readFrontend = (...segments: string[]) => readFileSync(frontendFile(...segments), 'utf8');

describe('ui accent, font, and color-scheme tokens', () => {
  it('does not keep the ChatGPT teal #10a37f as a dialog default', () => {
    const dialogCss = readFrontend('apps/shared/dialog.css');
    const primaryBlock = extractRuleBlock(dialogCss, '.app-dialog-btn.primary');
    const primaryHoverBlock = extractRuleBlock(dialogCss, '.app-dialog-btn.primary:hover');

    expect(dialogCss).not.toMatch(/#10a37f/i);
    expect(primaryBlock).toMatch(/var\(--color-accent,\s*#0052cc\)/i);
    expect(primaryHoverBlock).toMatch(/var\(--color-accent,\s*#0052cc\)/i);
  });

  it('does not load Google Fonts and drops unused Noto Sans SC', () => {
    const sources = [
      readFrontend('apps/teacher/src/tailwind.css'),
      readFrontend('apps/student/src/tailwind.css'),
      readFrontend('apps/teacher/index.html'),
      readFrontend('apps/student/index.html'),
      readFrontend('apps/shared/dialog.css'),
      readFrontend('vite.teacher.config.ts'),
      readFrontend('vite.student.config.ts'),
    ];

    for (const source of sources) {
      expect(source).not.toMatch(/fonts\.googleapis/i);
      expect(source).not.toContain('Noto Sans SC');
    }

    const teacherCss = sources[0];
    const studentCss = sources[1];
    const fontSans =
      /--font-sans:\s*['"]PingFang SC['"],\s*['"]Helvetica Neue['"],\s*Arial,\s*sans-serif;/;
    expect(teacherCss).toMatch(fontSans);
    expect(studentCss).toMatch(fontSans);
  });

  it('declares light-dark color-scheme and dark token overrides', () => {
    const teacherCss = readFrontend('apps/teacher/src/tailwind.css');
    const studentCss = readFrontend('apps/student/src/tailwind.css');
    const teacherVite = readFrontend('vite.teacher.config.ts');
    const studentVite = readFrontend('vite.student.config.ts');

    expect(extractRuleBlock(teacherCss, ':root')).toContain('color-scheme: light dark;');
    expect(extractRuleBlock(studentCss, ':root')).toContain('color-scheme: light dark;');
    expect(teacherCss).toContain('@media (prefers-color-scheme: dark)');
    expect(studentCss).toContain('@media (prefers-color-scheme: dark)');
    expect(teacherVite).toContain("theme_color: '#0052CC'");
    expect(studentVite).toContain("theme_color: '#0052CC'");
    expect(teacherVite).toContain("background_color: '#FAFBFC'");
    expect(studentVite).toContain("background_color: '#FAFBFC'");
    expect(teacherVite).not.toContain('#2f6d6b');
    expect(studentVite).not.toContain('#2f6d6b');
    expect(readFrontend('apps/teacher/index.html')).toContain('viewport-fit=cover');
    expect(readFrontend('apps/student/index.html')).toContain('viewport-fit=cover');
  });

  it('does not mix theme colors with literal white in app TSX', () => {
    const roots = [
      readFrontend('apps/teacher/src/features/layout/TeacherAdminPanel.tsx'),
      readFrontend('apps/teacher/src/features/workbench/TeacherWorkbench.tsx'),
      readFrontend('apps/teacher/src/features/chat/ChatMessages.tsx'),
      readFrontend('apps/student/src/features/home/StudentTodayHome.tsx'),
      readFrontend('apps/student/src/features/home/TodayTaskCard.tsx'),
      readFrontend('apps/teacher/src/features/workbench/tabs/MemoryTab.tsx'),
    ];
    for (const source of roots) {
      expect(source).not.toMatch(/%,\s*white\)/i);
      expect(source).not.toMatch(/text-\[#[0-9a-f]{3,8}\]/i);
    }
  });

  const relativeLuminance = (hex: string): number => {
    const raw = hex.replace('#', '');
    const n = raw.length === 3 ? raw.split('').map((c) => c + c).join('') : raw;
    const channel = (value: string) => {
      const srgb = parseInt(value, 16) / 255;
      return srgb <= 0.03928 ? srgb / 12.92 : ((srgb + 0.055) / 1.055) ** 2.4;
    };
    const r = channel(n.slice(0, 2));
    const g = channel(n.slice(2, 4));
    const b = channel(n.slice(4, 6));
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };

  const contrast = (hexA: string, hexB: string): number => {
    const l1 = relativeLuminance(hexA);
    const l2 = relativeLuminance(hexB);
    const lighter = Math.max(l1, l2);
    const darker = Math.min(l1, l2);
    return (lighter + 0.05) / (darker + 0.05);
  };

  it('dark on-accent contrast is at least 4.5', () => {
    expect(contrast('#071427', '#4c9aff')).toBeGreaterThanOrEqual(4.5);
    expect(contrast('#8ab4f8', '#22262e')).toBeGreaterThanOrEqual(4.5);
    expect(contrast('#8ab4f8', '#1b3a6b')).toBeGreaterThanOrEqual(4.5);
    expect(contrast('#ffc14d', '#22262e')).toBeGreaterThanOrEqual(4.5);
  });

  it('global focus-visible rule exists in teacher and student css', () => {
    const teacherCss = readFrontend('apps/teacher/src/tailwind.css');
    const studentCss = readFrontend('apps/student/src/tailwind.css');
    expect(teacherCss).toMatch(/:focus-visible\s*\{/);
    expect(studentCss).toMatch(/:focus-visible\s*\{/);
    expect(teacherCss).toContain('prefers-reduced-motion');
    expect(studentCss).toContain('prefers-reduced-motion');
    const rail = extractRuleBlock(teacherCss, '.teacher-rail-cta');
    expect(rail).toContain('color: var(--color-on-accent)');
  });

  it('apps tsx have no raw text-[#] or bg-[#]', () => {
    const walk = (dir: string, acc: string[] = []): string[] => {
      for (const name of readdirSync(dir)) {
        const full = path.join(dir, name);
        const st = statSync(full);
        if (st.isDirectory()) walk(full, acc);
        else if (name.endsWith('.tsx')) acc.push(full);
      }
      return acc;
    };
    const files = [...walk(frontendFile('apps/teacher')), ...walk(frontendFile('apps/student'))];
    expect(files.length).toBeGreaterThan(10);
    for (const file of files) {
      const source = readFileSync(file, 'utf8');
      expect(source, file).not.toMatch(/text-\[#[0-9a-fA-F]{3,8}\]/);
      expect(source, file).not.toMatch(/bg-\[#[0-9a-fA-F]{3,8}\]/);
      expect(source, file).not.toMatch(/bg-accent text-white/);
    }
    const teacherEb = readFrontend('apps/teacher/src/ErrorBoundary.tsx');
    const studentEb = readFrontend('apps/student/src/ErrorBoundary.tsx');
    expect(teacherEb).not.toContain('#444');
    expect(studentEb).not.toContain('#444');
    expect(teacherEb).not.toContain('#f6f6f6');
    expect(studentEb).not.toContain('#f6f6f6');
  });
});
