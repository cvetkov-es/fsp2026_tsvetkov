import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { Button, ErrorText, LinkButton, Meter, Pill, Segmented, TechChip } from '../components/ui'

describe('UI-кит редизайна', () => {
  it('buttons carry the variant and stay native', async () => {
    const click = vi.fn()
    render(<MemoryRouter>
      <Button onClick={click}>Главная</Button>
      <Button variant="danger" disabled>Удалить</Button>
      <LinkButton to="/lab" variant="secondary">Лаборатория</LinkButton>
    </MemoryRouter>)
    await userEvent.click(screen.getByRole('button', { name: 'Главная' }))
    expect(click).toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Главная' })).toHaveClass('bg-primary')
    expect(screen.getByRole('button', { name: 'Удалить' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Удалить' })).toHaveClass('text-danger')
    expect(screen.getByRole('link', { name: 'Лаборатория' })).toHaveAttribute('href', '/lab')
  })

  it('errors are alerts in the danger colour, an empty error renders nothing', () => {
    const { container } = render(<><ErrorText>{null}</ErrorText><ErrorText>Сеть недоступна</ErrorText></>)
    expect(screen.getByRole('alert')).toHaveTextContent('Сеть недоступна')
    expect(screen.getByRole('alert')).toHaveClass('text-danger')
    expect(container.querySelectorAll('[role="alert"]')).toHaveLength(1)
  })

  it('meter clamps the value and exposes it to assistive tech', () => {
    render(<Meter value={1.4} label="Надёжность вывода" />)
    expect(screen.getByRole('meter', { name: 'Надёжность вывода' })).toHaveAttribute('aria-valuenow', '100')
  })

  it('segmented control marks the chosen option and reports changes', async () => {
    const change = vi.fn()
    render(<Segmented label="Кто вы" value="candidate" onChange={change}
      options={[{ value: 'candidate', label: 'Я ищу работу' }, { value: 'employer', label: 'Я работодатель' }]} />)
    expect(screen.getByRole('button', { name: 'Я ищу работу' })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByRole('button', { name: 'Я работодатель' }))
    expect(change).toHaveBeenCalledWith('employer')
  })

  it('tech chips tell confirmed from declared', () => {
    render(<><TechChip tech="SQL" confirmed /><TechChip tech="Docker" confirmed={false} declaredLabel /><Pill tone="success">подтверждён</Pill></>)
    expect(screen.getByText('SQL ✓')).toHaveClass('bg-ink')
    expect(screen.getByText('Docker · заявлено')).toHaveClass('text-muted')
    expect(screen.getByText('подтверждён')).toHaveClass('text-success')
  })
})
