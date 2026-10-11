import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ItemPrompt } from '../components/test/ItemPrompt'

describe('ItemPrompt', () => {
  it('renders text, code and tables; reports copy attempts', () => {
    const onCopy = vi.fn()
    render(<ItemPrompt onCopyAttempt={onCopy} prompt={{
      text: 'Сколько строк вернёт запрос?', code: 'SELECT 1;', language: 'sql', options: null, steps: null,
      answer_hint: 'Целое число', tables: [{ name: 'customers', columns: ['id', 'name'], rows: [[1, 'Анна'], [2, null]] }],
    }} />)
    expect(screen.getByText('Сколько строк вернёт запрос?')).toBeInTheDocument()
    expect(screen.getByText('SELECT 1;')).toBeInTheDocument()
    expect(screen.getByText('Анна')).toBeInTheDocument()
    expect(screen.getByText('NULL')).toBeInTheDocument()
    screen.getByText('SELECT 1;').dispatchEvent(new Event('copy', { bubbles: true }))
    expect(onCopy).toHaveBeenCalled()
  })
})
