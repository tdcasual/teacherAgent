import { describe, expect, it } from 'vitest';

import { renderMarkdown } from './markdown';

describe('renderMarkdown KaTeX layout', () => {
  it('keeps KaTeX inline styles needed for subscript layout', () => {
    const html = renderMarkdown('并判断 $R_1$、$R_2$、$R_3$ 之间的连接关系');
    expect(html).toContain('class="katex"');
    expect(html).toContain('style=');
  });

  it('does not allow arbitrary inline styles from markdown input', () => {
    const html = renderMarkdown('测试 <span style="color:red">文本</span> 与 $R_1$');
    expect(html).toContain('class="katex"');
    expect(html).not.toContain('color:red');
  });
});
