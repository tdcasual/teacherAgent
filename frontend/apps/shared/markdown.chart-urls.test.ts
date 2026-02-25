import { describe, expect, it } from 'vitest';

import { absolutizeChartImageUrls } from './markdown';

const applyChartUrls = absolutizeChartImageUrls as (
  html: string,
  apiBase: string,
  accessToken?: string,
) => string;

describe('absolutizeChartImageUrls', () => {
  it('appends access_token for chart img and links when token is provided', () => {
    const source =
      '<p><img src="/charts/chr_1/main.png" alt="图" /><a href="/charts/chr_1/main.png">下载</a></p>';
    const html = applyChartUrls(source, 'http://localhost:8000', 'token.abc');
    expect(html).toContain(
      'src="http://localhost:8000/charts/chr_1/main.png?access_token=token.abc"',
    );
    expect(html).toContain(
      'href="http://localhost:8000/charts/chr_1/main.png?access_token=token.abc"',
    );
  });

  it('preserves existing chart query params and appends access_token with ampersand', () => {
    const source = '<p><img src="/charts/chr_1/main.png?download=1" alt="图" /></p>';
    const html = applyChartUrls(source, 'http://localhost:8000', 'token.abc');
    expect(html).toContain(
      'src="http://localhost:8000/charts/chr_1/main.png?download=1&access_token=token.abc"',
    );
  });
});
