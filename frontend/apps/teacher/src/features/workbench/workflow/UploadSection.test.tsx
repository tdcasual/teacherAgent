import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import * as teacherAuth from '../../auth/teacherAuth';
import UploadSection from './UploadSection';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

const baseProps = {
  assignmentKind: 'problem_set' as const,
  uploadCardCollapsed: false,
  setUploadCardCollapsed: vi.fn(),
  formatUploadJobSummary: () => 'upload',
  uploadJobInfo: null,
  uploadAssignmentId: 'HW-1',
  handleUploadAssignment: vi.fn(),
  setUploadAssignmentId: vi.fn(),
  uploadDate: '',
  setUploadDate: vi.fn(),
  uploadDueAt: '',
  setUploadDueAt: vi.fn(),
  uploadSubjectId: 'physics',
  setUploadSubjectId: vi.fn(),
  uploadScope: 'class' as const,
  setUploadScope: vi.fn(),
  uploadClassName: '',
  setUploadClassName: vi.fn(),
  uploadStudentIds: '',
  setUploadStudentIds: vi.fn(),
  setUploadFiles: vi.fn(),
  setUploadAnswerFiles: vi.fn(),
  uploading: false,
  uploadError: '',
  uploadStatus: '',
};

describe('UploadSection', () => {
  it('gates upload copy by assignment kind', () => {
    vi.spyOn(teacherAuth, 'readTeacherAccessToken').mockReturnValue('');
    const { rerender } = render(<UploadSection {...baseProps} assignmentKind="problem_set" />);
    expect(
      screen.getByText('上传后将解析题目与答案，并生成 8 点描述。解析完成后请发布草稿。'),
    ).toBeTruthy();

    rerender(<UploadSection {...baseProps} assignmentKind="scenario" />);
    expect(
      screen.getByText(
        '上传后将从材料提取作业说明（brief）。非做题允许 0 题。解析完成后请发布草稿。',
      ),
    ).toBeTruthy();
    expect(screen.queryByText(/8 点描述/)).toBeNull();
  });

  it('falls back to a static subject list when roster is empty', () => {
    vi.spyOn(teacherAuth, 'readTeacherAccessToken').mockReturnValue('');
    render(<UploadSection {...baseProps} uploadSubjectId="generic" uploadScope="public" />);

    const subject = screen.getByLabelText('学科') as HTMLSelectElement;
    expect(subject.value).toBe('generic');
    expect(Array.from(subject.options).map((option) => option.value)).toEqual([
      'physics',
      'math',
      'generic',
    ]);
    expect(screen.getByLabelText('截止日期（可选）')).toBeTruthy();
    expect(screen.queryByRole('button', { name: '考试' })).toBeNull();
  });

  it('uses GET /teacher/roster for subject and class dropdowns', async () => {
    vi.spyOn(teacherAuth, 'readTeacherAccessToken').mockReturnValue('teacher-token');
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        ok: true,
        items: [
          { teacher_id: 't_zhang', subject_id: 'physics', class_name: '高二2403班' },
          { teacher_id: 't_zhang', subject_id: 'math', class_name: '高二2403班' },
        ],
      }),
    }));
    vi.stubGlobal('fetch', fetchMock);

    render(<UploadSection {...baseProps} />);

    await waitFor(() => {
      const subject = screen.getByLabelText('学科') as HTMLSelectElement;
      expect(Array.from(subject.options).map((option) => option.value)).toEqual([
        'physics',
        'math',
      ]);
    });
    const classField = screen.getByLabelText('班级（班级作业必填）') as HTMLSelectElement;
    expect(classField.tagName).toBe('SELECT');
    expect(Array.from(classField.options).map((option) => option.value)).toEqual([
      '',
      '高二2403班',
    ]);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/teacher/roster'),
      expect.objectContaining({
        headers: { Authorization: 'Bearer teacher-token' },
      }),
    );
  });

  it('refetches roster after teacher login', async () => {
    const tokenSpy = vi.spyOn(teacherAuth, 'readTeacherAccessToken').mockReturnValue('');
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        ok: true,
        items: [{ teacher_id: 't_zhang', subject_id: 'physics', class_name: '高二2403班' }],
      }),
    }));
    vi.stubGlobal('fetch', fetchMock);

    render(<UploadSection {...baseProps} uploadSubjectId="generic" uploadScope="public" />);

    expect(fetchMock).not.toHaveBeenCalled();
    tokenSpy.mockReturnValue('teacher-token');
    window.dispatchEvent(new Event(teacherAuth.TEACHER_AUTH_EVENT));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/teacher/roster'),
        expect.objectContaining({
          headers: { Authorization: 'Bearer teacher-token' },
        }),
      );
    });
    await waitFor(() => {
      const subject = screen.getByLabelText('学科') as HTMLSelectElement;
      expect(Array.from(subject.options).map((option) => option.value)).toContain('physics');
    });
  });
});
