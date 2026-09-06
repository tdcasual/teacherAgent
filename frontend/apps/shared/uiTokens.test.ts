import { readFileSync } from 'node:fs';
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
    expect(teacherCss).toContain(
      '--font-sans: "PingFang SC", "Helvetica Neue", Arial, sans-serif;',
    );
    expect(studentCss).toContain(
      '--font-sans: "PingFang SC", "Helvetica Neue", Arial, sans-serif;',
    );
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
});
