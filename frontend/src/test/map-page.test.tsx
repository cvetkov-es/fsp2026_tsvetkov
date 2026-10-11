import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import MapPage from '../pages/employer/MapPage'

vi.mock('../api/employer', async (orig) => ({
  ...(await orig<typeof import('../api/employer')>()),
  getMap: vi.fn(async () => ({ cells: [
    { specialization: 'backend', grade: 'middle', confirmed: 142, unconfirmed: 63 },
    { specialization: 'data', grade: 'senior', confirmed: 9, unconfirmed: 6 },
  ] })),
}))

describe('Карта категорий', () => {
  it('links every cell and saturates it by the share of the fullest cell', async () => {
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><MapPage /></MemoryRouter></QueryClientProvider>)
    // в jsdom между строчными span имени ссылки пробелов нет — отсюда \s*
    const strong = await screen.findByRole('link', { name: /^142\s*подтверждены/ })
    expect(strong).toHaveAttribute('href', '/employer/map/backend/middle')
    expect(strong).toHaveTextContent('+63 не подтвердили')
    expect(strong).toHaveAttribute('data-heat', '1.00')
    expect(screen.getByRole('link', { name: /^9\s*подтверждены/ })).toHaveAttribute('data-heat', '0.06')
    expect(screen.getAllByRole('link', { name: /^0\s*подтверждены/ })).toHaveLength(7)  // пустые ячейки тоже кликабельны
  })
})
