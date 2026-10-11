import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import SkillsPage from '../pages/candidate/SkillsPage'

vi.mock('../api/skills', () => ({
  getSkills: vi.fn(async () => [
    { code: 'sql', title: 'SQL', summary: 'Выборки и соединения', techs: ['SQL', 'PostgreSQL'], status: 'not_taken', available: true, available_at: null,
      active_attempt_id: null, recommended: true, bank_ready: true, format: 'test', items: 6, minutes: null },
    { code: 'devops', title: 'DevOps и контейнеры', summary: 'Образы и пайплайны', techs: ['Docker'], status: 'passed', available: false, available_at: null,
      active_attempt_id: null, recommended: false, bank_ready: true, format: 'test', items: 6, minutes: null },
  ]),
  startSkill: vi.fn(),
}))

describe('Навыки: сетка и карточка', () => {
  it('opens the recommended skill first and switches the detail on click', async () => {
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><SkillsPage /></MemoryRouter></QueryClientProvider>)
    expect(await screen.findByRole('heading', { name: 'SQL' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /SQL/ })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByRole('button', { name: /DevOps и контейнеры/ }))
    expect(screen.getByRole('heading', { name: 'DevOps и контейнеры' })).toBeInTheDocument()
    expect(screen.getByText('Технологии навыка отмечены ✓ в профиле и в подборке.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /пройти · 6 заданий/i })).not.toBeInTheDocument()
  })
})
