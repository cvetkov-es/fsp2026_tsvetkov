import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import CandidateHome from '../pages/candidate/CandidateHome'

afterEach(() => vi.restoreAllMocks())

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })

const open = { allowed: true, available_at: null, reasons: [] }
const meta = {
  specializations: [
    { code: 'backend', title: 'Backend', test_available: true },
    { code: 'data', title: 'Data / Analytics', test_available: false },
  ],
  grades: [],
}

function setup(profile: object, { demo = false, skills = [] as object[], demand = null as object | null } = {}) {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input)
    if (url.endsWith('/candidate/profile')) return json(profile)
    if (url.endsWith('/candidate/meta')) return json(meta)
    if (url.endsWith('/candidate/tests/availability')) return json({ junior: open, middle: open, senior: open })
    if (url.endsWith('/candidate/attempts')) return json([])
    if (url.endsWith('/demo/personas')) return demo ? json([]) : json({ code: 'not_found', title: 'Не найдено' }, 404)
    if (url.endsWith('/candidate/skills')) return json(skills)
    if (url.endsWith('/candidate/demand')) return demand ? json(demand) : json({ code: 'not_found', title: 'Не найдено' }, 404)
    return json({}, 404)
  })
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={qc}><MemoryRouter><CandidateHome /></MemoryRouter></QueryClientProvider>)
}

describe('CandidateHome', () => {
  it('confirmed candidate is offered the next grade and a retest, not a lower grade', async () => {
    setup({ specialization: 'backend', claimed_grade: 'middle', grade_status: 'confirmed', confirmed_grade: 'middle', status_grade: 'middle' })
    expect(await screen.findByRole('link', { name: /тест на senior/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /пересдать middle/i })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /junior/i })).not.toBeInTheDocument()
  })

  it('not-confirmed label names the grade of the attempt, not the current claim', async () => {
    setup({ specialization: 'backend', claimed_grade: 'junior', grade_status: 'not_confirmed', confirmed_grade: null, status_grade: 'middle' })
    expect(await screen.findByRole('heading', { name: 'Middle не подтверждён' })).toBeInTheDocument()
  })

  it('specialization without a bank shows that the test is not open yet', async () => {
    setup({ specialization: 'data', claimed_grade: 'middle', grade_status: 'not_tested', confirmed_grade: null, status_grade: null })
    expect(await screen.findByText(/тест по направлению готовится/i)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /пройти тест/i })).not.toBeInTheDocument()
  })

  it('demo cooldown reset is shown whenever demo mode is on', async () => {
    setup({ specialization: 'backend', claimed_grade: 'middle', grade_status: 'not_tested', confirmed_grade: null, status_grade: null }, { demo: true })
    expect(await screen.findByRole('button', { name: /разрешить пересдачу сейчас/i })).toBeInTheDocument()
  })

  it('recommends one skill from the declared stack', async () => {
    setup({ specialization: 'backend', claimed_grade: 'middle', grade_status: 'not_tested', confirmed_grade: null, status_grade: null }, {
      skills: [
        { code: 'sql', title: 'SQL', summary: '', techs: ['SQL', 'PostgreSQL'], status: 'not_taken', available: true, available_at: null, active_attempt_id: null, recommended: true, bank_ready: true },
        { code: 'devops', title: 'DevOps и контейнеры', summary: '', techs: ['Docker'], status: 'not_taken', available: true, available_at: null, active_attempt_id: null, recommended: true, bank_ready: true },
      ],
    })
    expect(await screen.findByText('SQL: подтвердите SQL, PostgreSQL за 6 заданий')).toBeInTheDocument()
    expect(screen.queryByText(/DevOps/)).not.toBeInTheDocument()  // процесс 2.5: по одному навыку
  })

  it('offers the initiative links and shows the demand block', async () => {
    setup({ specialization: 'backend', claimed_grade: 'middle', grade_status: 'confirmed', confirmed_grade: 'middle', status_grade: 'middle' },
      { demand: { category: 'Backend · Middle', enough: false, companies: null, min_companies: 5, window_days: 30, top: [], skills: [] } })
    expect(await screen.findByRole('link', { name: /«Хочу к вам»/ })).toHaveAttribute('href', '/candidate/companies')
    expect(screen.getByRole('link', { name: 'Задачи компаний' })).toHaveAttribute('href', '/candidate/tasks')
    expect(screen.getByRole('link', { name: 'Вакансии' })).toHaveAttribute('href', '/candidate/vacancies')
    expect(await screen.findByText(/Покажем спрос, когда/)).toBeInTheDocument()
  })
})
