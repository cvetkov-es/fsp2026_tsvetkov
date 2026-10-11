import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { resetCooldowns } from '../api/assessment'
import { getSkills } from '../api/skills'
import SkillsPage from '../pages/candidate/SkillsPage'

vi.mock('../api/skills', () => ({
  getSkills: vi.fn(async () => [
    { code: 'devops', title: 'DevOps и контейнеры', summary: 'Docker', techs: ['Docker'], status: 'failed', available: true, available_at: '2026-09-01T10:00:00Z', active_attempt_id: null, recommended: false, bank_ready: true },
  ]),
  startSkill: vi.fn(),
}))
vi.mock('../api/assessment', async (orig) => ({ ...(await orig<typeof import('../api/assessment')>()), resetCooldowns: vi.fn(async () => undefined) }))
vi.mock('../api/client', async (orig) => ({ ...(await orig<typeof import('../api/client')>()), api: vi.fn(async () => []) }))  // демо-режим: персоны есть

describe('SkillsPage in demo mode', () => {
  it('hides a retake date that has passed and resets cooldowns without the survey', async () => {
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><SkillsPage /></MemoryRouter></QueryClientProvider>)
    expect(await screen.findByText('не подтверждён')).toBeInTheDocument()  // пересдача уже доступна — без даты
    await userEvent.click(await screen.findByRole('button', { name: 'Разрешить пересдачу сейчас (демо)' }))
    expect(resetCooldowns).toHaveBeenCalled()
    expect(vi.mocked(getSkills).mock.calls.length).toBeGreaterThan(1)
  })
})
