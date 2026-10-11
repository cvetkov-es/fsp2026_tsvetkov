import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { DisputeReason, Review } from '../api/hiring'
import ReviewsPage from '../pages/candidate/ReviewsPage'

const reviews: Review[] = [
  { id: 'v1', company: 'Корп', value: 'below', grade: 'middle', specialization: 'backend', at: '2026-10-08T10:00:00Z', state: 'pending', effective_at: '2026-10-15T10:00:00Z', can_dispute: true },
  { id: 'v2', company: 'Байкал Софт', value: 'meets', grade: 'middle', specialization: 'backend', at: '2026-09-01T10:00:00Z', state: 'active', effective_at: '2026-09-08T10:00:00Z', can_dispute: false },
]
const api = vi.hoisted(() => ({
  getReviews: vi.fn<() => Promise<Review[]>>(),
  disputeReview: vi.fn<(id: string, reason: DisputeReason, comment: string, answeredAt: string) => Promise<Review[]>>(),
}))
vi.mock('../api/hiring', async (orig) => ({ ...(await orig<typeof import('../api/hiring')>()), ...api }))

beforeEach(() => { vi.clearAllMocks(); api.getReviews.mockResolvedValue(reviews); api.disputeReview.mockResolvedValue(reviews) })

describe('ReviewsPage', () => {
  it('lists private reviews and disputes one by facts', async () => {
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><ReviewsPage /></MemoryRouter></QueryClientProvider>)
    expect(await screen.findByText('Оценка: ниже ожиданий (грейд Middle) · 08.10.2026')).toBeInTheDocument()
    expect(screen.getByText('вступит в силу 15.10.2026')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Оспорить' })).toHaveLength(1) // действующую уже не оспорить
    const toggle = screen.getByRole('button', { name: 'Оспорить' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(toggle)
    expect(screen.getByRole('button', { name: 'Скрыть' })).toHaveAttribute('aria-expanded', 'true')
    const send = screen.getByRole('button', { name: 'Оспорить' })
    expect(send).toBeDisabled()
    await userEvent.click(screen.getByLabelText('Собеседования не было'))
    await userEvent.type(screen.getByLabelText('Комментарий для модератора'), 'Созвона не было')
    await userEvent.click(send)
    // answered_at — версия оценки, которую видел кандидат: если компания её изменила, сервер ответит 409
    expect(api.disputeReview).toHaveBeenCalledWith('v1', 'no_interview', 'Созвона не было', '2026-10-08T10:00:00Z')
  })
})
