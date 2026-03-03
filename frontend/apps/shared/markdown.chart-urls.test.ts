import { describe, expect, it } from 'vitest';

import { absolutizeChartImageUrls } from './markdown';

const applyChartUrls = absolutizeChartImageUrls as (html: string, apiBase: string) => string;

describe('absolutizeChartImageUrls', () => {
  it('absolutizes chart img and links without query access token', () => {
    const source =
      '<p><img src="/charts/chr_1/main.png" alt="图" /><a href="/charts/chr_1/main.png">下载</a></p>';
    const html = applyChartUrls(source, 'http://localhost:8000');
    expect(html).toContain('src="http://localhost:8000/charts/chr_1/main.png"');
    expect(html).toContain('href="http://localhost:8000/charts/chr_1/main.png"');
    expect(html).not.toContain('access_token=');
  });

  it('preserves existing chart query params without appending auth token', () => {
    const source = '<p><img src="/charts/chr_1/main.png?download=1" alt="图" /></p>';
    const html = applyChartUrls(source, 'http://localhost:8000');
    expect(html).toContain('src="http://localhost:8000/charts/chr_1/main.png?download=1"');
    expect(html).not.toContain('access_token=');
  });
});
