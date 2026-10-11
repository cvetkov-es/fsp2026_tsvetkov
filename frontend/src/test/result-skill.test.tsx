import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import type { AttemptState } from '../api/assessment'
import ResultView from '../pages/candidate/ResultView'

const state: AttemptState = {
  id: 'a1', target_grade: 'skill', express: false, status: 'completed', stage: 'finished', n_answered: 6, phase2_total: 0,
  phase2_answered: 0, bank_exhausted: false, item: null,
  result: { decision: 'confirmed', phrase: 'Навык «SQL» подтверждён · решено 5 из 6', reliability: 0.91, border: false, confident: false, express: false },
}

describe('ResultView for a skill', () => {
  it('shows the skill phrase and leads back to skills, without grade wording', () => {
    render(<MemoryRouter><ResultView state={state} /></MemoryRouter>)
    expect(screen.getByText('Навык «SQL» подтверждён · решено 5 из 6')).toBeInTheDocument()
    expect(screen.getByText(/отмечены ✓ в профиле/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'К навыкам' })).toHaveAttribute('href', '/candidate/skills')
    expect(screen.queryByText(/Тест адаптивный/)).not.toBeInTheDocument()
  })
})
