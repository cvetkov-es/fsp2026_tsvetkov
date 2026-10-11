import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import type { FspProfile } from '../api/fsp'
import { FspSection, FspView } from '../components/candidate/FspSection'

vi.mock('../api/fsp', async (orig) => ({ ...(await orig<typeof import('../api/fsp')>()), getFsp: vi.fn(async () => ({ status: 'LINKED', summary: 'ФСП: призёр 1 старта', last_sync_at: null, results: [], online: { count: 0, disciplines: 0 }, ranks: [] })) }))

const base: FspProfile = { status: 'NOT_LINKED', summary: null, last_sync_at: null, results: [], online: { count: 0, disciplines: 0 }, ranks: [] }

describe('FspView', () => {
  it('is neutral without FSP and offers linking', () => {
    render(<FspView fsp={base} onUnlink={vi.fn()} />)
    expect(screen.getByText(/Результатов ФСП пока нет/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Привязать FSP ID' })).toHaveAttribute('href', '/api/v1/auth/fsp/start?purpose=link')
    expect(screen.queryByText(/0 достижений/)).not.toBeInTheDocument()
  })

  it('shows levels, team line, online in one line, ranks and not counted results', async () => {
    const onUnlink = vi.fn()
    const fsp: FspProfile = {
      ...base, status: 'LINKED', summary: 'ФСП: призёр 2 стартов', last_sync_at: '2026-10-09T10:00:00Z',
      results: [
        { competition_title: 'Кубок России, финал', discipline_title: 'продуктовое программирование', date: '2025-11-22', place: 2, field_size: 20, tier: 'prize', tier_title: 'призовое место', team_name: 'Byte Force', team_size: 3, counted: true, note: null },
        { competition_title: 'Чемпионат Москвы', discipline_title: 'алгоритмическое программирование', date: '2026-09-27', place: 1, field_size: 80, tier: 'winner', tier_title: 'победа', team_name: null, team_size: null, counted: false, note: 'предварительный протокол' },
      ],
      online: { count: 10, disciplines: 1 }, ranks: [{ rank: 'KMS', title: 'КМС', valid_until: '2028-12-20', valid: true }],
    }
    render(<FspView fsp={fsp} onUnlink={onUnlink} />)
    expect(screen.getByText('ФСП: призёр 2 стартов')).toBeInTheDocument()
    expect(screen.getByText(/в составе команды «Byte Force» \(3 чел\.\)/)).toBeInTheDocument()
    expect(screen.getByText(/не засчитано: предварительный протокол/)).toBeInTheDocument()
    expect(screen.getByText(/Онлайн-отборов: 10/)).toBeInTheDocument()
    expect(screen.getByText(/КМС: действует до/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /отвязать/i }))
    expect(onUnlink).toHaveBeenCalled()
  })

  it('explains stale data with the snapshot date', () => {
    render(<FspView fsp={{ ...base, status: 'SYNC_STALE', last_sync_at: '2026-10-01T10:00:00Z', summary: 'ФСП: финалист 1 старта' }} onUnlink={vi.fn()} />)
    expect(screen.getByText(/ФСП сейчас недоступен. Показаны данные на 01\.10\.2026/)).toBeInTheDocument()
  })

  it('says data is not received yet when the first sync failed', () => {
    render(<FspView fsp={{ ...base, status: 'SYNC_STALE', last_sync_at: null }} onUnlink={vi.fn()} />)
    expect(screen.getByText(/Данные ФСП ещё не пришли. Нажмите «Обновить из ФСП»/)).toBeInTheDocument()
  })

  it('keeps FSP ID as the login of a password-less account after revoke', () => {
    render(<FspView fsp={{ ...base, status: 'CONSENT_REVOKED', login_via_fsp: true }} onUnlink={vi.fn()} />)
    expect(screen.getByText(/Входить через FSP ID можно, как раньше/)).toBeInTheDocument()
  })
})

function Search() {
  return <p data-testid="search">{useLocation().search}</p>
}

describe('FspSection', () => {
  it('shows the link result once and clears it from the address', async () => {
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={['/candidate/profile?fsp=linked']}>
      <FspSection /><Search />
    </MemoryRouter></QueryClientProvider>)
    expect(await screen.findByText('ФСП: призёр 1 старта')).toBeInTheDocument()
    expect(screen.getByText('FSP ID привязан, результаты обновлены.')).toBeInTheDocument()
    expect(screen.getByTestId('search')).toHaveTextContent(/^$/)
  })
})
