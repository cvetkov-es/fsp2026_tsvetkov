import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import type { Prompt } from '../api/assessment'
import { verdictReady } from '../components/test/verdict'
import { VerdictInput } from '../components/test/VerdictInput'

const clarify = ['Включать ли границу?', 'Что вернуть для пустого?', 'Как быть с None?', 'Учитывать ли отрицательные?']
const py: Prompt = { text: 'Сумма больше 5', code: 'def solve(xs):\n    return 0\n    pass', language: 'python', options: null, tables: [],
  steps: null, answer_hint: null, input_classes: ['empty', 'boundary'], clarify }
const sql: Prompt = { ...py, code: 'SELECT 1\nFROM t', language: 'sql', input_classes: [], tables: [{ name: 't', columns: ['id', 'v'], rows: [[1, 2]] }] }

function Harness({ prompt }: { prompt: Prompt }) {
  const [v, setV] = useState<unknown>(null)
  return (
    <>
      <VerdictInput prompt={prompt} value={v} onChange={setV} maxRows={2} />
      <output data-testid="value">{JSON.stringify(v)}</output>
      <output data-testid="ready">{String(verdictReady(v))}</output>
    </>
  )
}
const value = () => JSON.parse(screen.getByTestId('value').textContent ?? 'null')

describe('VerdictInput', () => {
  it('asks for a line and a breaking class when the solution is wrong', async () => {
    render(<Harness prompt={py} />)
    await userEvent.click(screen.getByLabelText('Неверно'))
    expect(screen.getByRole('combobox')).toHaveTextContent('123') // три строки кода
    await userEvent.selectOptions(screen.getByRole('combobox'), '2')
    await userEvent.click(screen.getByLabelText('Граница диапазона'))
    expect(screen.getByTestId('ready')).toHaveTextContent('false') // без уверенности не отправить
    await userEvent.click(screen.getByLabelText('Низкая'))
    expect(value()).toEqual({ verdict: 'defect', line: 2, input_class: 'boundary', confidence: 'low' })
    expect(screen.getByTestId('ready')).toHaveTextContent('true')
  })

  it('offers the same clarification list for every verdict', async () => {
    render(<Harness prompt={py} />)
    await userEvent.click(screen.getByLabelText('Нужно уточнить требование'))
    await userEvent.click(screen.getByLabelText('Как быть с None?'))
    await userEvent.click(screen.getByLabelText('Высокая'))
    expect(value()).toEqual({ verdict: 'clarify', clarify: 2, confidence: 'high' })
  })

  it('collects SQL data within the row limit instead of input classes', async () => {
    render(<Harness prompt={sql} />)
    await userEvent.click(screen.getByLabelText('Неверно'))
    expect(screen.queryByText('Ломающий вход')).not.toBeInTheDocument()
    const add = screen.getByRole('button', { name: '+ строка в t' })
    await userEvent.click(add)
    await userEvent.type(screen.getByLabelText('t: строка 1, v'), 'NULL')
    await userEvent.click(add)
    expect(add).toBeDisabled() // лимит строк
    expect(value().rows).toEqual({ t: [['', 'NULL'], ['', '']] })
  })

  it('is not ready for «Неверно» without a breaking input, and explains classes and decimals', async () => {
    render(<Harness prompt={py} />)
    await userEvent.click(screen.getByLabelText('Неверно'))
    await userEvent.selectOptions(screen.getByRole('combobox'), '2')
    await userEvent.click(screen.getByLabelText('Высокая'))
    expect(screen.getByTestId('ready')).toHaveTextContent('false') // без ломающего входа балл потерян бы молча
    expect(screen.getByText(/Выберите, какой вход ломает решение/)).toBeInTheDocument()
  })

  it('tells how decimals are typed in SQL data', async () => {
    render(<Harness prompt={sql} />)
    await userEvent.click(screen.getByLabelText('Неверно'))
    expect(screen.getByText(/Дробную часть отделяйте точкой или запятой/)).toBeInTheDocument()
  })
})
