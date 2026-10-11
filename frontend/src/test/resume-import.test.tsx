import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ResumeImport } from '../components/candidate/ResumeImport'

const draft = { source: 'llm', specialization: 'backend', recommended_grade: 'middle', experience_years: 4.2, stack: ['Python', 'Docker'], unknown_terms: [],
  formats: ['remote'], city: 'Казань', domains: ['финтех'], full_name: 'Иван Петров', contacts: { email: 'i@example.ru' }, warnings: [] }
vi.mock('../api/profile', () => ({ uploadResume: vi.fn(async () => draft) }))

describe('ResumeImport', () => {
  it('shows suggestions from the resume and applies them on demand', async () => {
    const onApply = vi.fn()
    render(<ResumeImport onApply={onApply} />)
    await userEvent.upload(screen.getByLabelText(/заполнить из резюме/i), new File(['%PDF'], 'cv.pdf', { type: 'application/pdf' }))
    expect(await screen.findByText(/Стек: Python, Docker/)).toBeInTheDocument()
    expect(screen.getByText(/с помощью ИИ/)).toBeInTheDocument()
    expect(screen.getByText(/Подсказка по грейду: Middle/)).toBeInTheDocument()
    expect(onApply).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: /применить к профилю/i }))
    expect(onApply).toHaveBeenCalledWith(draft)
  })

  it('lets the same file be chosen again after an error', async () => {
    render(<ResumeImport onApply={vi.fn()} />)
    const input = screen.getByLabelText(/заполнить из резюме/i) as HTMLInputElement
    await userEvent.upload(input, new File(['%PDF'], 'cv.pdf', { type: 'application/pdf' }))
    expect(await screen.findByText(/Стек: Python, Docker/)).toBeInTheDocument()
    expect(input.value).toBe('')
  })
})
