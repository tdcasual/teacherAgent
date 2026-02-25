import { describe, expect, it } from 'vitest'

import { renderStreamingPlainText } from './markdown'

describe('renderStreamingPlainText', () => {
  it('escapes html and preserves new lines as <br/>', () => {
    const html = renderStreamingPlainText('A<&>"\'\nB')
    expect(html).toBe('A&lt;&amp;&gt;&quot;&#39;<br/>B')
  })

  it('normalizes CRLF before rendering', () => {
    const html = renderStreamingPlainText('第一行\r\n第二行\r第三行')
    expect(html).toBe('第一行<br/>第二行<br/>第三行')
  })
})

