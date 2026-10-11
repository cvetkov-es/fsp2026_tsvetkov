import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import TeamsPage from '../pages/employer/TeamsPage'

const h = vi.hoisted(() => ({
  create: vi.fn(async (_body: unknown) => ({ id: 'g1' })),
  groups: [] as object[],
}))
const member = (ref: string, alias: string, minor = false) => ({ ref, alias, specialization: 'backend', grade: 'middle', grade_status: 'confirmed', minor })
vi.mock('../api/fsp', async (orig) => ({
  ...(await orig<typeof import('../api/fsp')>()),
  getTeams: vi.fn(async () => [{ team_id: 't1', team_name: 'Byte Force', competition_title: 'Кубок', discipline_title: 'продуктовое программирование', date: '2025-11-22',
    place: 2, field_size: 20, tier: 'prize', team_size: 3, on_platform: 3, cohesion: 2, members: [member('a1', 'B-M-AAAA'), member('b2', 'B-M-BBBB'), member('c3', 'B-J-CCCC', true)] }]),
}))
vi.mock('../api/employer', async (orig) => ({
  ...(await orig<typeof import('../api/employer')>()),
  listNeeds: vi.fn(async () => [
    { id: 'n1', title: 'Бэкенд', status: 'active', salary_from: 200000, salary_to: 300000, gross_net: 'gross', employment: 'internship', contact_method: 'chat' },
    { id: 'n2', title: 'Закрытая', status: 'closed', salary_from: 1, salary_to: 2, gross_net: 'net', employment: 'full', contact_method: 'chat' },
  ]),
}))
vi.mock('../api/groups', async (orig) => ({
  ...(await orig<typeof import('../api/groups')>()),
  createGroup: (b: unknown) => h.create(b),
  getGroups: vi.fn(async () => h.groups),
  getGroupLimits: vi.fn(async () => ({ ttl_days: 7, min_team: 2 })),
}))

const setup = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <MemoryRouter initialEntries={['/employer/teams']}><Routes>
    <Route path="/employer/teams" element={<TeamsPage />} /><Route path="/employer/groups/:id" element={<p>страница группы</p>} />
  </Routes></MemoryRouter></QueryClientProvider>)

describe('inviting a whole team', () => {
  beforeEach(() => { vi.clearAllMocks(); h.groups = [] })

  it('builds the group with a fork per member prefilled from the need and goes to the group page', async () => {
    setup()
    await userEvent.click(await screen.findByRole('button', { name: 'Пригласить команду' }))
    expect(screen.getByText(/Каждый участник занимает место в квоте потребности/)).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'Закрытая' })).not.toBeInTheDocument()  // только активные потребности
    expect(screen.getByLabelText('B-M-AAAA: вилка от, ₽')).toHaveValue('200000')
    await userEvent.clear(screen.getByLabelText('B-M-BBBB: вилка до, ₽'))
    await userEvent.type(screen.getByLabelText('B-M-BBBB: вилка до, ₽'), '280000')
    await userEvent.type(screen.getByLabelText('B-J-CCCC: часов в неделю'), '20')  // только у кандидата 14–17 лет
    expect(screen.queryByLabelText('B-M-AAAA: часов в неделю')).not.toBeInTheDocument()
    await userEvent.clear(screen.getByLabelText('Минимальный состав'))
    await userEvent.type(screen.getByLabelText('Минимальный состав'), '2')
    const d = new Date(Date.now() + 3 * 86_400_000)
    fireEvent.change(screen.getByLabelText('Ответить до'), { target: { value: d.toISOString().slice(0, 10) } })
    await userEvent.type(screen.getByLabelText('Почему вы'), 'Сыгранная команда')
    await userEvent.type(screen.getByLabelText('Следующий шаг'), 'Созвон с командой')
    await userEvent.click(screen.getByRole('button', { name: 'Отправить командное приглашение' }))
    expect(h.create).toHaveBeenCalledWith(expect.objectContaining({
      need_id: 'n1', team_id: 't1', min_size: 2, why_you: 'Сыгранная команда', next_step: 'Созвон с командой', gross_net: 'gross',
      deadline: expect.stringMatching(/^\d{4}-\d\d-\d\dT.*Z$/),
      members: [
        { ref: 'a1', salary_from: 200000, salary_to: 300000 },
        { ref: 'b2', salary_from: 200000, salary_to: 280000 },
        { ref: 'c3', salary_from: 200000, salary_to: 300000, hours_per_week: 20 },
      ],
    }))
    expect(await screen.findByText('страница группы')).toBeInTheDocument()
  })

  it('lets the employer leave a member out, and the minimum cannot exceed those chosen', async () => {
    setup()
    await userEvent.click(await screen.findByRole('button', { name: 'Пригласить команду' }))
    await userEvent.click(screen.getByLabelText('Приглашать B-J-CCCC'))  // без юниора часы не нужны
    await userEvent.type(screen.getByLabelText('Почему вы'), 'Два сильных')
    await userEvent.type(screen.getByLabelText('Следующий шаг'), 'Созвон')
    fireEvent.change(screen.getByLabelText('Ответить до'), { target: { value: new Date(Date.now() + 3 * 86_400_000).toISOString().slice(0, 10) } })
    await userEvent.click(screen.getByRole('button', { name: 'Отправить командное приглашение' }))
    expect(h.create).toHaveBeenCalledWith(expect.objectContaining({ min_size: 2, members: [expect.objectContaining({ ref: 'a1' }), expect.objectContaining({ ref: 'b2' })] }))
  })

  it('does not send until the minimum is valid and shows the server error as is', async () => {
    h.create.mockRejectedValueOnce(new ApiError(409, 'quota_exceeded', 'Квоты приглашений по этой потребности не хватает на всю команду', 'Ответа ждут 2 из 3, для команды нужно 3'))
    setup()
    await userEvent.click(await screen.findByRole('button', { name: 'Пригласить команду' }))
    const send = screen.getByRole('button', { name: 'Отправить командное приглашение' })
    expect(send).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Почему вы'), 'Команда')
    await userEvent.type(screen.getByLabelText('Следующий шаг'), 'Созвон')
    fireEvent.change(screen.getByLabelText('Ответить до'), { target: { value: new Date(Date.now() + 2 * 86_400_000).toISOString().slice(0, 10) } })
    await userEvent.clear(screen.getByLabelText('Минимальный состав'))
    await userEvent.type(screen.getByLabelText('Минимальный состав'), '9')
    expect(send).toBeDisabled()  // больше состава
    await userEvent.clear(screen.getByLabelText('Минимальный состав'))
    await userEvent.type(screen.getByLabelText('Минимальный состав'), '3')
    expect(send).toBeDisabled()  // у участника 14–17 лет не указаны часы в неделю
    await userEvent.type(screen.getByLabelText('B-J-CCCC: часов в неделю'), '20')
    await userEvent.click(send)
    expect(await screen.findByRole('alert')).toHaveTextContent('Квоты приглашений по этой потребности не хватает на всю команду: Ответа ждут 2 из 3, для команды нужно 3')
  })

  it('lists the groups already sent with links to them', async () => {
    h.groups = [{ id: 'g7', team_name: 'Byte Force', need_title: 'Бэкенд', size: 3, deadline: '2026-10-12T10:00:00Z', state: 'open' }]
    setup()
    expect(await screen.findByRole('link', { name: /«Byte Force» · Бэкенд/ })).toHaveAttribute('href', '/employer/groups/g7')
  })
})
