import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import { saveDetails } from '../api/profile'
import ProfileDetailsPage from '../pages/candidate/ProfileDetailsPage'

vi.mock('../api/fsp', async (orig) => ({ ...(await orig<typeof import('../api/fsp')>()), getFsp: vi.fn(async () => ({ status: 'NOT_LINKED', summary: null, last_sync_at: null, results: [], online: { count: 0, disciplines: 0 }, ranks: [] })) }))
vi.mock('../api/profile', () => ({
  getDetails: vi.fn(async () => ({ full_name: null, contacts: {}, experience_years: null, formats: [], city: null, domains: [], salary_threshold: null, salary_gross_net: 'net', open_until: null })),
  getStack: vi.fn(async () => ({ items: [{ tech: 'SQL', state: 'confirmed' }, { tech: 'Docker', state: 'declared' }, { tech: 'Kubernetes', state: 'confirmed' }], declared: ['Docker', 'Kubernetes'], unknown: [] })),
  getMarket: vi.fn(async () => ({ median_net: 210000, n: 40 })),
  saveDetails: vi.fn(), saveStack: vi.fn(), openWindow: vi.fn(), uploadResume: vi.fn(), PROFILE_PDF_URL: '/api/v1/candidate/profile/pdf',
}))
vi.mock('../api/complaints', () => ({ getMyCases: vi.fn(async () => []) }))
vi.mock('../api/employer', async (orig) => ({ ...(await orig<typeof import('../api/employer')>()), getStackDict: vi.fn(async () => []) }))

describe('ProfileDetailsPage', () => {
  it('shows market median hint, stack states and private contacts note', async () => {
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><ProfileDetailsPage /></MemoryRouter></QueryClientProvider>)
    expect(await screen.findByText(/медиана по вашей категории 210 000 ₽ на руки/)).toBeInTheDocument()
    expect(await screen.findByText(/SQL ✓/)).toBeInTheDocument()
    expect(screen.getByText(/Docker · заявлено/)).toBeInTheDocument()
    expect(screen.getByText(/Компания увидит их после того, как вы примете её приглашение/)).toBeInTheDocument()
    // в выборе стека — всё заявленное, даже то, что уже подтверждено навыком
    expect(screen.getByRole('button', { name: 'Kubernetes ×' })).toBeInTheDocument()
    expect(screen.getByLabelText(/сферы/i)).toBeInTheDocument()
  })

  it('shows a save error instead of failing silently', async () => {
    vi.mocked(saveDetails).mockRejectedValueOnce(new ApiError(422, 'validation_error', 'Проверьте поля формы'))
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><ProfileDetailsPage /></MemoryRouter></QueryClientProvider>)
    await userEvent.click(await screen.findByRole('button', { name: 'Сохранить' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Проверьте поля формы')
  })
})
