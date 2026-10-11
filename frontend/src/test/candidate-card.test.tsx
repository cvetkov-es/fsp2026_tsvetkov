import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { Card } from '../api/employer'
import { CandidateCard } from '../components/employer/CandidateCard'

const card: Card = {
  ref: 'abcd1234', alias: 'B-M-ABCD', grade: 'middle', grade_status: 'confirmed', block: 1, fit_level: 'высокое',
  readiness: { level: 'высокая', tooltip: 'вилка покрывает ожидания · окно поиска открыто до 20.10' }, stack: [{ tech: 'Python', state: 'confirmed' }, { tech: 'Docker', state: 'declared' }],
  skills: [], experience_years: 3, formats: ['remote'], city: 'Казань', conflicts: [], pinned: false, express: false, filter_mismatch: null,
  explanation: { lines: ['Middle подтверждён тестом · сильнее 82% категории', 'Стек: Python ✓, Docker (заявлено)', 'Истории ФСП нет, навыки оценены по тесту'], missing: ['Docker: заявлено, не подтверждено'], counterfactual: 'Если подтвердить Docker, кандидат поднимется на 2 позиции' },
}

describe('CandidateCard', () => {
  it('shows alias, three lines, readiness tooltip; details on expand; pin callback', async () => {
    const onPin = vi.fn()
    render(<CandidateCard card={card} onPin={onPin} />)
    expect(screen.getByText('B-M-ABCD')).toBeInTheDocument()
    expect(screen.getByText(/сильнее 82% категории/)).toBeInTheDocument()
    expect(screen.getByTitle(/вилка покрывает ожидания/)).toHaveTextContent('Готовность: высокая')
    expect(screen.queryByText(/поднимется на 2 позиции/)).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /подробнее/i }))
    expect(screen.getByText(/поднимется на 2 позиции/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /в шортлист/i }))
    expect(onPin).toHaveBeenCalledWith('abcd1234', true)
  })

  it('shows confirmed skills', () => {
    render(<CandidateCard card={{ ...card, skills: ['sql', 'ai'] }} />)
    expect(screen.getByText(/Навыки: SQL, Работа с ИИ/)).toBeInTheDocument()
  })

  it('shows only the positive interview badge', () => {
    render(<CandidateCard card={{ ...card, interview_badge: 'Подтверждено на собеседованиях (3)' }} />)
    expect(screen.getByText('Подтверждено на собеседованиях (3)')).toBeInTheDocument()
  })
})
