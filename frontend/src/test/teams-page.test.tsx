import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { getTeams } from '../api/fsp'
import TeamsPage from '../pages/employer/TeamsPage'

vi.mock('../api/fsp', async (orig) => ({
  ...(await orig<typeof import('../api/fsp')>()),
  getTeams: vi.fn(async () => [{ team_id: 't', team_name: 'Byte Force', competition_title: 'Кубок России по продуктовому программированию 2025, финал', discipline_title: 'продуктовое программирование', date: '2025-11-22', place: 2, field_size: 20, tier: 'prize', team_size: 3, on_platform: 2, cohesion: 2, members: [{ ref: 'a1', alias: 'B-S-A1B2', specialization: 'backend', grade: 'senior', grade_status: 'confirmed' }, { ref: 'b2', alias: 'F-M-C3D4', specialization: 'frontend', grade: 'middle', grade_status: 'not_confirmed' }] }]),
}))

describe('TeamsPage', () => {
  it('lists prize teams with members on platform and cohesion', async () => {
    render(<QueryClientProvider client={new QueryClient()}><TeamsPage /></QueryClientProvider>)
    expect(await screen.findByText('«Byte Force»')).toBeInTheDocument()
    expect(screen.getByText(/на платформе 2 из 3 · сыгранность 2\.0/)).toBeInTheDocument()
    expect(screen.getByText(/B-S-A1B2 · Senior ✓/)).toBeInTheDocument()
  })

  it('falls back to the team id when the name is unknown', async () => {
    vi.mocked(getTeams).mockResolvedValueOnce([{ team_id: 'neural-north-cr25', team_name: null, competition_title: 'Чемпионат России', discipline_title: 'продуктовое программирование', date: '2025-11-28', place: 1, field_size: 30, tier: 'winner', team_size: 4, on_platform: 2, cohesion: 1, members: [] }])
    render(<QueryClientProvider client={new QueryClient()}><TeamsPage /></QueryClientProvider>)
    expect(await screen.findByText('«neural-north-cr25»')).toBeInTheDocument()
  })
})
