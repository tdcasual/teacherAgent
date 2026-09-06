import { describe, expect, it } from 'vitest';

import { selectComposerHint } from './studentUiSelectors';

describe('selectComposerHint', () => {
  it('tells verified students that chat is coaching, not submit', () => {
    expect(
      selectComposerHint({
        verifiedStudent: { student_id: 'S1', student_name: '测试' },
        pendingChatJobId: '',
        sending: false,
      }),
    ).toContain('对话不会记为提交');
  });
});
