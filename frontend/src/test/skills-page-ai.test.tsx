import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import SkillsPage from '../pages/candidate/SkillsPage'

const start = vi.fn<(code: string, body: unknown) => Promise<{ id: string }>>(async () => ({ id: 'a1' }))
vi.mock('../api/skills', () => ({
  getSkills: vi.fn(async () => [
    { code: 'ai', title: 'Работа с ИИ', summary: 'ИИ разрешён', techs: ['Copilot'], status: 'not_taken', available: true, available_at: null,
      active_attempt_id: null, recommended: false, bank_ready: true, format: 'ai', items: 12, minutes: 10 },
  ]),
  startSkill: (code: string, body: unknown) => start(code, body),
}))

describe('SkillsPage, «Работа с ИИ»', () => {
  it('states that AI is allowed and how the format works', async () => {
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><SkillsPage /></MemoryRouter></QueryClientProvider>)
    expect(await screen.findByText(/12 готовых решений за 10 минут/)).toBeInTheDocument()
    await userEvent.click(screen.getByLabelText(/ИИ разрешён/))
    await userEvent.click(screen.getByLabelText('Обязуюсь проходить без помощи других людей'))
    await userEvent.click(screen.getByRole('button', { name: 'Пройти · 12 решений за 10 минут' }))
    expect(start).toHaveBeenCalledWith('ai', { accept_rules: true, pledge: true, extra_time: false })
  })
})
