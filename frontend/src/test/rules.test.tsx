import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import RulesPage from '../pages/candidate/RulesPage'

vi.mock('../api/client', () => ({
  api: vi.fn(async () => ({ texts: [{ type: 'automated_rules', version: 'v', title: 'Согласие с автоматическими правилами', body: 'Текст правил' }], presets: {} })),
  ApiError: class extends Error {},
}))

describe('RulesPage', () => {
  it('start disabled until both rules consent and pledge are checked', async () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={['/test/rules?grade=middle&express=1']}><RulesPage /></MemoryRouter>
      </QueryClientProvider>,
    )
    const start = await screen.findByRole('button', { name: /начать/i })
    expect(start).toBeDisabled()
    await userEvent.click(screen.getByLabelText(/согласен с автоматическими правилами/i))
    expect(start).toBeDisabled()
    await userEvent.click(screen.getByLabelText(/обязуюсь/i))
    expect(start).toBeEnabled()
    expect(screen.getByText(/экспресс/i)).toBeInTheDocument()
  })

  it('double click on start sends one request; retest of the confirmed grade warns first', async () => {
    const { api } = await import('../api/client')
    const calls: string[] = []
    vi.mocked(api).mockImplementation(async (path: string) => {
      calls.push(path)
      if (path === '/consents/texts') return { texts: [], presets: {} }
      if (path === '/candidate/profile') return { specialization: 'backend', claimed_grade: 'middle', grade_status: 'confirmed', confirmed_grade: 'middle', status_grade: 'middle' }
      return new Promise(() => {}) // старт «висит» — второй клик не должен уйти
    })
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={['/test/rules?grade=middle']}><RulesPage /></MemoryRouter>
      </QueryClientProvider>,
    )
    expect(await screen.findByText(/Новая попытка заменит текущий результат/)).toBeInTheDocument()
    await userEvent.click(screen.getByLabelText(/согласен с автоматическими правилами/i))
    await userEvent.click(screen.getByLabelText(/обязуюсь/i))
    const start = screen.getByRole('button', { name: /начать/i })
    await userEvent.click(start)
    await userEvent.click(start)
    expect(calls.filter((p) => p === '/candidate/attempts')).toHaveLength(1)
  })
})
