import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { AttemptState } from '../api/assessment'
import ResultView from '../pages/candidate/ResultView'

const h = vi.hoisted(() => ({ object: vi.fn(async (_a: string, _c: string) => ({ case_id: 'c1', due_at: '2026-11-08T10:00:00Z' })) }))
vi.mock('../api/complaints', () => ({ objectToDecision: (a: string, c: string) => h.object(a, c) }))

const state: AttemptState = {
  id: 'a1', target_grade: 'middle', express: false, status: 'completed', stage: 'finished', n_answered: 6, phase2_total: 0,
  phase2_answered: 0, bank_exhausted: false, item: null,
  result: { decision: 'not_confirmed', phrase: 'Middle не подтверждён · решено 2 из 6', reliability: 0.9, border: false, confident: false, express: false },
}

describe('objection to the automated decision (art. 16, 152-FZ)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('needs a comment of at least 10 characters and tells the answer deadline', async () => {
    render(<MemoryRouter><ResultView state={state} /></MemoryRouter>)
    await userEvent.click(screen.getByText('Почему такой вывод'))
    await userEvent.click(screen.getByRole('button', { name: 'Возразить против автоматического решения (ст. 16 152-ФЗ)' }))
    const send = screen.getByRole('button', { name: 'Отправить возражение' })
    expect(send).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Почему вы не согласны с решением'), 'Задания были с опечатками')
    await userEvent.click(send)
    expect(h.object).toHaveBeenCalledWith('a1', 'Задания были с опечатками')
    expect(await screen.findByText('Ответим до 08.11 в разделе «Мои обращения»')).toBeInTheDocument()
  })

  it('is offered only for the grade test, not for a skill', () => {
    render(<MemoryRouter><ResultView state={{ ...state, target_grade: 'skill' }} /></MemoryRouter>)
    expect(screen.queryByText(/ст\. 16/)).not.toBeInTheDocument()
  })
})
