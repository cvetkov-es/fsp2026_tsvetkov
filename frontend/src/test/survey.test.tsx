import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import SurveyPage from '../pages/candidate/SurveyPage'

afterEach(() => vi.restoreAllMocks())

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })

describe('SurveyPage', () => {
  it('marks directions without a test and shows a save error instead of failing silently', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = String(input)
      if (url.endsWith('/candidate/meta')) return json({
        specializations: [{ code: 'backend', title: 'Backend', test_available: true }, { code: 'data', title: 'Data / Analytics', test_available: false }],
        grades: [{ code: 'middle', title: 'Middle', description: '' }],
      })
      if (url.endsWith('/candidate/profile')) return json({ specialization: 'backend', claimed_grade: 'middle', grade_status: 'not_tested', confirmed_grade: null, status_grade: null })
      if (url.endsWith('/candidate/profile/survey') && init?.method === 'PUT') return json({ code: 'attempt_in_progress', title: 'Сначала завершите начатый тест' }, 409)
      return json({}, 404)
    })
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><SurveyPage /></MemoryRouter></QueryClientProvider>)
    const data = await screen.findByRole('button', { name: /data/i })
    expect(data).toHaveTextContent(/тест готовится/i)
    await userEvent.click(data)
    await userEvent.click(screen.getByRole('button', { name: /сохранить/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Сначала завершите начатый тест')
  })
})
