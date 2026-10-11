import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import SkillsPage from '../pages/candidate/SkillsPage'

const start = vi.fn<(code: string, body: unknown) => Promise<{ id: string }>>(async () => ({ id: 'a1' }))
vi.mock('../api/skills', () => ({
  getSkills: vi.fn(async () => [
    { code: 'sql', title: 'SQL', summary: 'Выборки', techs: ['SQL', 'PostgreSQL'], status: 'not_taken', available: true, available_at: null, active_attempt_id: null, recommended: true, bank_ready: true },
    { code: 'devops', title: 'DevOps и контейнеры', summary: 'Docker', techs: ['Docker'], status: 'failed', available: false, available_at: '2026-10-23T10:00:00Z', active_attempt_id: null, recommended: false, bank_ready: true },
    { code: 'ml_basics', title: 'Основы ML', summary: 'pandas', techs: ['pandas'], status: 'passed', available: false, available_at: null, active_attempt_id: null, recommended: false, bank_ready: true },
  ]),
  startSkill: (code: string, body: unknown) => start(code, body),
}))

describe('SkillsPage', () => {
  it('shows statuses honestly and starts a skill test after rules', async () => {
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={['/candidate/skills']}>
      <Routes><Route path="/candidate/skills" element={<SkillsPage />} /><Route path="/test/:id" element={<p>тест</p>} /></Routes>
    </MemoryRouter></QueryClientProvider>)
    expect(await screen.findByText('Рекомендуем')).toBeInTheDocument()
    expect(screen.getByText(/не подтверждён · пересдача с 23\.10\.2026/)).toBeInTheDocument()
    expect(screen.getByText('подтверждён ✓')).toBeInTheDocument()
    expect(screen.getByText(/SQL, PostgreSQL/)).toBeInTheDocument()
    const go = screen.getAllByRole('button', { name: /пройти · 6 заданий/i })[0]
    expect(go).toBeDisabled()
    await userEvent.click(screen.getAllByLabelText(/принимаю правила/i)[0])
    await userEvent.click(screen.getAllByLabelText(/без посторонней помощи/i)[0])
    await userEvent.click(go)
    expect(start).toHaveBeenCalledWith('sql', { accept_rules: true, pledge: true, extra_time: false })
    expect(await screen.findByText('тест')).toBeInTheDocument()
  })
})
