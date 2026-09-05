import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import * as teacherAuth from '../auth/teacherAuth'
import AdminSchoolPanel from './AdminSchoolPanel'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('AdminSchoolPanel', () => {
  it('creates a teacher and shows temp password as a copy-once text node', async () => {
    vi.spyOn(teacherAuth, 'readTeacherAccessToken').mockReturnValue('admin-token')
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/auth/admin/teacher/list') && (!init || init.method === 'GET' || !init.method)) {
        return {
          ok: true,
          json: async () => ({ ok: true, items: [] }),
        }
      }
      if (url.includes('/auth/admin/teacher/create')) {
        return {
          ok: true,
          json: async () => ({
            ok: true,
            teacher_id: 't_zhang',
            temp_password: 'TempPass12ab',
            teacher: { teacher_id: 't_zhang', teacher_name: '张老师' },
          }),
        }
      }
      throw new Error(`unexpected url ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<AdminSchoolPanel />)

    expect(document.querySelector('[class*="min-w-[720px]"]') || screen.getByRole('region', { name: '学校管理' })).toBeTruthy()
    fireEvent.change(screen.getByLabelText('教师姓名'), { target: { value: '张老师' } })
    fireEvent.click(screen.getByRole('button', { name: '创建教师' }))

    const passwordNode = await screen.findByText('TempPass12ab')
    expect(passwordNode.tagName).not.toBe('INPUT')
    expect(passwordNode.getAttribute('value')).toBeNull()
    expect(passwordNode.getAttribute('data-password')).toBeNull()

    const copyButton = screen.getByRole('button', { name: '复制一次' })
    fireEvent.click(copyButton)
    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith('TempPass12ab')
      expect(screen.queryByRole('button', { name: '复制一次' })).toBeNull()
    })
  })
})
