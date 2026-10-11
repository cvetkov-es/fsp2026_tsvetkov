import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import CompaniesPage from '../pages/candidate/CompaniesPage'
import TasksPage from '../pages/candidate/TasksPage'
import VacanciesPage from '../pages/candidate/VacanciesPage'
import EmployerTasksPage from '../pages/employer/TasksPage'
import EmployerVacanciesPage from '../pages/employer/VacanciesPage'

const down = () => { throw new ApiError(500, 'error', 'Сервер недоступен') }
vi.mock('../api/initiative', () => ({ getCompanies: vi.fn(async () => down()) }))
vi.mock('../api/tasks', async (orig) => ({
  ...(await orig<typeof import('../api/tasks')>()),
  getTasks: vi.fn(async () => down()), getCompanyTasks: vi.fn(async () => down()),
  getTaskLimits: vi.fn(async () => ({ text_max: 2000, ttl_days: 14 })),
}))
vi.mock('../api/vacancies', async (orig) => ({
  ...(await orig<typeof import('../api/vacancies')>()),
  getVacancies: vi.fn(async () => down()), getApplications: vi.fn(async () => down()), getCompanyVacancies: vi.fn(async () => down()),
}))
vi.mock('../api/employer', async (orig) => ({
  ...(await orig<typeof import('../api/employer')>()),
  getCompany: vi.fn(async () => ({ id: 'k1', name: 'Корп', description: null, industry: null, contacts: {}, trust_level: 'L1' })),
  listNeeds: vi.fn(async () => []),
}))
vi.mock('../api/client', async (orig) => ({
  ...(await orig<typeof import('../api/client')>()),
  api: vi.fn(async () => ({ texts: [] })),
}))

const show = (el: React.ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <MemoryRouter>{el}</MemoryRouter></QueryClientProvider>)

describe('lists say so when they fail to load', () => {
  it.each([
    ['candidate companies', CompaniesPage],
    ['candidate tasks', TasksPage],
    ['candidate vacancies', VacanciesPage],
    ['employer tasks', EmployerTasksPage],
    ['employer vacancies', EmployerVacanciesPage],
  ])('%s', async (_name, Page) => {
    show(<Page />)
    expect((await screen.findAllByRole('alert'))[0]).toHaveTextContent('Сервер недоступен')
  })
})
