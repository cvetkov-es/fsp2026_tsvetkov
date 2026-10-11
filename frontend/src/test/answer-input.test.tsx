import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { AnswerInput } from '../components/test/AnswerInput'
import type { AnswerKind, Prompt } from '../api/assessment'

const base: Prompt = { text: 'q', code: null, language: null, options: null, tables: [], steps: null, answer_hint: null }

function Harness({ kind, prompt }: { kind: AnswerKind; prompt: Prompt }) {
  const [v, setV] = useState<unknown>(null)
  return (<><AnswerInput kind={kind} prompt={prompt} value={v} onChange={setV} /><output data-testid="v">{JSON.stringify(v)}</output></>)
}

describe('AnswerInput', () => {
  it('order: clicking steps builds sequence and can reset', async () => {
    render(<Harness kind="order" prompt={{ ...base, steps: ['Шаг А', 'Шаг Б', 'Шаг В'] }} />)
    await userEvent.click(screen.getByRole('button', { name: /Шаг Б/ }))
    await userEvent.click(screen.getByRole('button', { name: /Шаг А/ }))
    await userEvent.click(screen.getByRole('button', { name: /Шаг В/ }))
    expect(screen.getByTestId('v').textContent).toBe('[2,1,3]')
    await userEvent.click(screen.getByRole('button', { name: /сбросить/i }))
    expect(screen.getByTestId('v').textContent).toBe('[]')
  })

  it('choice: radio sets index', async () => {
    render(<Harness kind="choice" prompt={{ ...base, options: ['200', '201', '204'] }} />)
    await userEvent.click(screen.getByLabelText('201'))
    expect(screen.getByTestId('v').textContent).toBe('1')
  })

  it('number: free input', async () => {
    render(<Harness kind="number" prompt={base} />)
    await userEvent.type(screen.getByRole('textbox'), '1,5')
    expect(screen.getByTestId('v').textContent).toBe('"1,5"')
  })
  it('choice options are real radio buttons reachable from the keyboard', async () => {
    const onChange = vi.fn()
    const prompt = { text: '?', code: null, language: null, options: ['0', '1', '2'], tables: [], steps: null, answer_hint: null }
    render(<AnswerInput kind="choice" prompt={prompt} value={null} onChange={onChange} />)
    await userEvent.tab()
    expect(screen.getByRole('radio', { name: '0' })).toHaveFocus()
    await userEvent.keyboard('{ArrowDown}')
    expect(onChange).toHaveBeenLastCalledWith(1)
  })
})
