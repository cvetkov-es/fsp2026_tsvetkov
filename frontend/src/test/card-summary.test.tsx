import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { Card } from '../api/employer'
import { CandidateCard } from '../components/employer/CandidateCard'

const getSummary = vi.fn(async () => ({ text: 'Кандидат с подтверждённым Middle, Python подтверждён тестом.', source: 'llm' }))
vi.mock('../api/employer', async (orig) => ({ ...(await orig<typeof import('../api/employer')>()), getSummary: () => getSummary() }))

const card: Card = {
  ref: 'abcd1234', alias: 'B-M-ABCD', grade: 'middle', grade_status: 'confirmed', block: 1, fit_level: 'высокое', readiness: null,
  stack: [], skills: [], experience_years: null, formats: [], city: null, conflicts: [], pinned: false, express: false, filter_mismatch: null,
  explanation: { lines: ['Middle подтверждён тестом', 'Стек не указан', 'Истории ФСП нет — оценка навыков по тесту'], missing: [], counterfactual: null },
}

describe('CandidateCard summary', () => {
  it('requests the summary only when expanded and links the PDF', async () => {
    render(<QueryClientProvider client={new QueryClient()}><CandidateCard card={card} needId="n1" /></QueryClientProvider>)
    expect(getSummary).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: /подробнее/i }))
    expect(await screen.findByText(/Python подтверждён тестом/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /pdf-профиль/i })).toHaveAttribute('href', '/api/v1/employer/needs/n1/candidates/abcd1234/pdf')
  })
})
