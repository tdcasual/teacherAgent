import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import TeacherTaskStrip from './TeacherTaskStrip';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('TeacherTaskStrip', () => {
  it('renders an action-oriented assignment strip with a single primary CTA', () => {
    const onPrimaryAction = vi.fn();

    render(
      <TeacherTaskStrip
        statusLabel="待审核"
        tone="active"
        summary="状态：解析完成（待确认） · 作业编号：HW-20260314"
        nextStepLabel="下一步：继续审核草稿并确认创建作业"
        primaryActionLabel="查看草稿"
        onPrimaryAction={onPrimaryAction}
      />,
    );

    expect(screen.queryByText('今日重心')).toBeNull();
    expect(screen.getByText('今日作业')).toBeTruthy();
    expect(screen.queryByText('下一步')).toBeNull();
    expect(screen.getByText('待审核')).toBeTruthy();
    expect(screen.getByText('继续审核草稿并确认创建作业')).toBeTruthy();
    expect(screen.queryByText('状态：解析完成（待确认） · 作业编号：HW-20260314')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '查看草稿' }));
    expect(onPrimaryAction).toHaveBeenCalledTimes(1);
  });
});
