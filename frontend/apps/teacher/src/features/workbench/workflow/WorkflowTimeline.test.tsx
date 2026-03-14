import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import WorkflowTimeline from './WorkflowTimeline'

afterEach(() => {
  cleanup()
})

describe('WorkflowTimeline', () => {
  it('sorts entries by timestamp and highlights failure nodes', () => {
    render(
      <WorkflowTimeline
        entries={[
          { type: 'parse', summary: '解析完成', ts: '2026-03-14T10:00:00.000Z' },
          { type: 'review', summary: '审核失败：缺少知识点', ts: '2026-03-14T11:00:00.000Z' },
          { type: 'upload', summary: '上传成功', ts: '2026-03-14T09:00:00.000Z' },
        ]}
      />,
    )

    const items = screen.getAllByTestId('workflow-timeline-item')
    expect(items[0]?.textContent).toContain('审核失败：缺少知识点')
    expect(items[0]?.getAttribute('data-tone')).toBe('error')
    expect(items[1]?.textContent).toContain('解析完成')
  })

  it('renders a guidance empty state when there are no entries', () => {
    render(<WorkflowTimeline entries={[]} />)

    expect(screen.getByText('最近一次执行')).toBeTruthy()
    expect(screen.getByText('暂无执行记录')).toBeTruthy()
    expect(screen.getByText('先从上传区开始今天流程，系统会在这里持续回显解析与审核节点。')).toBeTruthy()
  })
})
