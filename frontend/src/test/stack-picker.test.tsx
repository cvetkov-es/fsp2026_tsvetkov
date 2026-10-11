import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { StackPicker } from '../components/StackPicker'

vi.mock('../api/employer', async (orig) => ({
  ...(await orig<typeof import('../api/employer')>()),
  getStackDict: vi.fn(async () => [
    { canonical: 'Kubernetes', category: 'devops', synonyms: ['k8s', 'кубер'] },
    { canonical: 'React', category: 'frontend', synonyms: ['reactjs', 'реакт'] },
  ]),
}))

describe('StackPicker', () => {
  it('finds technologies by synonyms, including Cyrillic ones', async () => {
    const onChange = vi.fn()
    render(<QueryClientProvider client={new QueryClient()}><StackPicker label="Стек" value={[]} onChange={onChange} /></QueryClientProvider>)
    await userEvent.type(screen.getByLabelText('Стек'), 'k8s')
    await userEvent.click(await screen.findByRole('button', { name: 'Kubernetes' }))
    expect(onChange).toHaveBeenCalledWith(['Kubernetes'])
    await userEvent.type(screen.getByLabelText('Стек'), 'реакт')
    expect(await screen.findByRole('button', { name: 'React' })).toBeInTheDocument()
  })
})
