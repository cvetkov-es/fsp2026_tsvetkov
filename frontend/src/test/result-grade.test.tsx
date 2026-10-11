import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import type { AttemptState } from '../api/assessment'
import ResultView from '../pages/candidate/ResultView'

const state = (result: AttemptState['result']): AttemptState => ({ id: 'a1', target_grade: 'middle', express: false, status: 'finished', stage: 'finished',
  n_answered: 12, phase2_total: 0, phase2_answered: 0, bank_exhausted: false, item: null, result })

describe('Итог теста на грейд', () => {
  it('shows reliability of the conclusion and the unlocked next test', () => {
    render(<MemoryRouter><ResultView state={state({ decision: 'confirmed', phrase: 'Middle подтверждён', reliability: 0.94, border: false, confident: true, express: false })} /></MemoryRouter>)
    expect(screen.getByRole('heading', { name: 'Middle подтверждён' })).toBeInTheDocument()
    expect(screen.getByRole('meter', { name: 'Надёжность вывода' })).toHaveAttribute('aria-valuenow', '94')
    expect(screen.getByText('94%')).toBeInTheDocument()
    expect(screen.getByText('Тест на Senior')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Пройти сейчас' })).toHaveAttribute('href', '/test/rules?grade=senior')
  })

  it('a negative result reports the reliability of "not confirmed" and offers no next test', () => {
    render(<MemoryRouter><ResultView state={state({ decision: 'not_confirmed', phrase: 'Middle не подтверждён', reliability: 0.1, border: true, confident: false, express: false })} /></MemoryRouter>)
    expect(screen.getByText('90%')).toBeInTheDocument()
    expect(screen.getByText(/на границе грейда/)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Пройти сейчас' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'В кабинет' })).toHaveAttribute('href', '/')
  })
})
