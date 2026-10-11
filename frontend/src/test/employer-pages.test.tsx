import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import CellPage from '../pages/employer/CellPage'
import NeedForm from '../pages/employer/NeedForm'

vi.mock('../api/employer', async (orig) => ({
  ...(await orig<typeof import('../api/employer')>()),
  getCell: vi.fn(async () => ({ items: [] })),
  getNeed: vi.fn(async () => { throw new ApiError(404, 'need_not_found', 'Потребность не найдена') }),
  getStackDict: vi.fn(async () => []),
}))

const at = (path: string, route: string, el: React.ReactNode) => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[path]}><Routes><Route path={route} element={el} /></Routes></MemoryRouter>
  </QueryClientProvider>)

describe('employer pages', () => {
  it('cell page titles the specialization by name', async () => {
    at('/employer/map/backend/middle', '/employer/map/:spec/:grade', <CellPage />)
    expect(await screen.findByRole('heading', { name: 'Backend · Middle' })).toBeInTheDocument()
  })

  it('need form reports a missing need instead of loading forever', async () => {
    at('/employer/needs/x/edit', '/employer/needs/:id/edit', <NeedForm />)
    expect(await screen.findByText(/Потребность не найдена/)).toBeInTheDocument()
  })
})
