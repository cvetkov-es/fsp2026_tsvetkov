import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import type { AttemptState } from '../api/assessment'
import ResultView from '../pages/candidate/ResultView'

const state: AttemptState = {
  id: 'a1', target_grade: 'skill', skill_code: 'ai', express: false, status: 'completed', stage: 'finished', n_answered: 12,
  phase2_total: 0, phase2_answered: 0, bank_exhausted: false, item: null,
  ai: { total: 12, time_left_s: null, minutes: 10, sql_max_rows: 20, pass_accuracy: 0.75, pass_miss: 0.25 },
  result: { decision: 'not_confirmed', phrase: 'Работа с ИИ: не подтверждено · верных вердиктов 10 из 12 · 8 мин', reliability: null,
    border: false, confident: false, express: false,
    ai: { passed: false, n: 12, answered: 12, correct: 10, accuracy: 0.833, miss_weighted: 0.333, false_reject: 0, minutes: 8, in_time: true } },
}

describe('ResultView for «Работа с ИИ»', () => {
  it('explains the verdict with metrics and their thresholds', () => {
    render(<MemoryRouter><ResultView state={state} /></MemoryRouter>)
    expect(screen.getByText(state.result!.phrase)).toBeInTheDocument()
    expect(screen.getByText('Точность: 83% (нужно от 75%)')).toBeInTheDocument()
    expect(screen.getByText('Принятые ошибки ИИ с учётом уверенности: 33% (допустимо до 25%)')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'К навыкам' })).toHaveAttribute('href', '/candidate/skills')
  })

  it('takes the retake delay from the server', () => {
    render(<MemoryRouter><ResultView state={{ ...state, ai: { ...state.ai!, cooldown_days: 21 } }} /></MemoryRouter>)
    expect(screen.getByText(/Пересдать можно через 21 день/)).toBeInTheDocument()
  })
})
