import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import LabeledField from './LabeledField'

describe('LabeledField', () => {
  it('associates the visible label with the control via htmlFor and id', () => {
    render(
      <LabeledField label="作业编号">
        <input />
      </LabeledField>,
    )
    const input = screen.getByLabelText('作业编号')
    expect(input.tagName).toBe('INPUT')
    expect(input.id).toBeTruthy()
    expect(input.id).toBe(screen.getByText('作业编号').closest('label')?.htmlFor)
  })
})
