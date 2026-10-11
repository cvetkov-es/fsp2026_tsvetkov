import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { getMyInvitations, type ContactStatus } from '../api/contacts'
import { useAuth, type Me } from '../auth/AuthContext'
import { FocusModeContext } from './focus-mode'
import { NotificationsBell } from './NotificationsBell'
import { LinkButton, Logo } from './ui'
import { useEscape } from './use-escape'

type Persona = { id: string; email: string; role: string }
type NavItem = { to: string; label: string; end?: boolean; badge?: number }

const ROLE_TITLE: Record<string, string> = { candidate: 'Кандидат', employer: 'Работодатель', moderator: 'Модератор', admin: 'Администратор' }
// Две основные роли засева (backend/app/demo/service.py, BASE_PERSONAS) — в переключателе, как в макете;
// модератор и остальные персоны — в списке «Ещё…», чтобы шапка помещалась в одну строку
const QUICK = [
  { email: 'demo.candidate@fsp-hiring.local', label: 'Кандидат' },
  { email: 'demo.employer@fsp-hiring.local', label: 'Работодатель' },
]
// У входа и регистрации своя двухколоночная сетка на всю ширину
const BLEED = ['/login', '/register', '/fsp/finish']
// Приглашения, которые ждут ответа кандидата
const AWAITING: ContactStatus[] = ['sent', 'viewed', 'offer_v2']

function navFor(role: string | undefined, awaiting: number): NavItem[] {
  if (role === 'candidate') {
    return [{ to: '/', label: 'Главная', end: true }, { to: '/candidate/skills', label: 'Навыки' },
      { to: '/candidate/invitations', label: 'Приглашения', badge: awaiting }, { to: '/candidate/reviews', label: 'Оценки' }, { to: '/lab', label: 'Лаборатория (для жюри)' }]
  }
  if (role === 'employer') {
    return [{ to: '/', label: 'Потребности', end: true }, { to: '/employer/map', label: 'Карта' },
      { to: '/employer/teams', label: 'Команды ФСП' }, { to: '/lab', label: 'Лаборатория (для жюри)' }]
  }
  if (role === 'moderator' || role === 'admin') return [{ to: '/moderation', label: 'Модерация' }, { to: '/lab', label: 'Лаборатория' }]
  return [{ to: '/lab', label: 'Лаборатория' }]
}

function DemoSwitch({ personas, me, onSwitch }: { personas: Persona[]; me: Me | null; onSwitch: (id: string) => void }) {
  const quick = QUICK.flatMap((q) => {
    const p = personas.find((x) => x.email === q.email)
    return p ? [{ ...q, id: p.id }] : []
  })
  const others = personas.filter((p) => !QUICK.some((q) => q.email === p.email))
  return (
    <div className="flex flex-wrap items-center gap-2">
      {quick.length > 0 && (
        <div role="group" aria-label="Демо: войти как" className="flex items-center gap-0.5 rounded-[10px] border border-line bg-canvas p-[3px]">
          <span aria-hidden="true" className="hidden px-2 text-[11px] font-semibold uppercase tracking-[0.06em] text-subtle sm:inline">Демо-персоны</span>
          {quick.map((q) => (
            <button key={q.id} type="button" aria-pressed={me?.id === q.id} onClick={() => onSwitch(q.id)}
              className={`rounded-[7px] px-2.5 py-1.5 text-[13px] font-medium transition ${me?.id === q.id ? 'bg-white text-ink shadow-sm' : 'text-muted hover:text-ink'}`}>
              {q.label}
            </button>
          ))}
        </div>
      )}
      {others.length > 0 && (
        <select aria-label="Другие демо-персоны" value="" onChange={(e) => onSwitch(e.target.value)}
          className="max-w-24 rounded-[10px] border border-line bg-white px-2 py-1.5 text-[13px] text-muted">
          <option value="" disabled>Ещё…</option>
          {others.map((p) => <option key={p.id} value={p.id}>{ROLE_TITLE[p.role] ?? p.role} · {p.email}</option>)}
        </select>
      )}
    </div>
  )
}

// «ivan.petrov@…» → «IP»: первые буквы частей имени почты
const initials = (email: string) => email.split('@')[0].split(/[._-]+/).filter(Boolean).slice(0, 2).map((s) => s[0]).join('').toUpperCase()

function ProfileMenu({ me, onLogout }: { me: Me; onLogout: () => void }) {
  const [open, setOpen] = useState(false)
  const item = 'block w-full rounded-lg px-3 py-2 text-left text-sm text-ink hover:bg-canvas'
  useEscape(open, () => setOpen(false))
  return (
    <div className="relative">
      <button type="button" aria-label="Меню профиля" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(!open)}
        className="grid size-8 place-items-center rounded-full bg-primary-soft text-[13px] font-semibold text-primary">
        {initials(me.email)}
      </button>
      {open && (
        <>
          <button type="button" aria-hidden="true" tabIndex={-1} className="fixed inset-0 z-10 cursor-default" onClick={() => setOpen(false)} />
          <div className="absolute right-0 z-20 mt-2 w-64 rounded-xl border border-line bg-white p-2 shadow-lg">
            <p className="truncate px-3 py-2 text-[13px] text-muted">{me.email} · {ROLE_TITLE[me.role] ?? me.role}</p>
            {me.role === 'candidate' && <Link to="/candidate/profile" className={item} onClick={() => setOpen(false)}>Профиль и условия</Link>}
            {me.role === 'employer' && <Link to="/employer/company" className={item} onClick={() => setOpen(false)}>Компания</Link>}
            <button type="button" className={item} onClick={() => { setOpen(false); onLogout() }}>Выйти</button>
          </div>
        </>
      )}
    </div>
  )
}

export default function Layout() {
  const { me, isLoading, logout, refresh } = useAuth()
  const nav = useNavigate()
  const { pathname } = useLocation()
  const [error, setError] = useState<string | null>(null)
  const [focus, setFocus] = useState(false)
  const run = async (action: () => Promise<unknown>) => {
    setError(null)
    try { await action() } catch (e) { setError(e instanceof ApiError ? e.title : 'Не удалось выполнить действие') }
  }
  const personas = useQuery({ queryKey: ['personas'], queryFn: () => api<Persona[]>('/demo/personas'), retry: false })
  // Тот же ключ, что на странице приглашений: счётчик и список не расходятся
  const invites = useQuery({ queryKey: ['my-invitations'], queryFn: getMyInvitations, enabled: me?.role === 'candidate' })
  const awaiting = invites.data?.filter((i) => AWAITING.includes(i.status)).length ?? 0
  const bleed = BLEED.includes(pathname) || (pathname === '/' && !me && !isLoading)
  const switchTo = (id: string) => run(async () => {
    await api('/demo/login-as', { method: 'POST', body: { user_id: id } })
    await refresh()
    nav('/')
  })
  return (
    <div className="flex min-h-screen flex-col">
      {/* На телефоне шапка в три строки: липкой она съела бы треть экрана, поэтому липнет только с sm */}
      <header inert={focus} aria-hidden={focus || undefined} className="relative z-10 border-b border-line bg-white/90 backdrop-blur sm:sticky sm:top-0">
        <div className="mx-auto flex min-h-16 max-w-[1240px] flex-wrap items-center gap-x-4 gap-y-3 px-4 py-2.5 sm:px-6">
          <Link to="/" className="flex items-center gap-2.5">
            <Logo /><span className="whitespace-nowrap text-[15px] font-semibold tracking-[-0.01em]">Обратный найм</span>
          </Link>
          <nav aria-label="Разделы" className="flex min-w-0 flex-[1_1_auto] flex-wrap gap-0.5">
            {navFor(me?.role, awaiting).map((n) => (
              <NavLink key={n.to} to={n.to} end={n.end}
                className={({ isActive }) => `flex items-center gap-2 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition ${isActive ? 'bg-canvas text-ink' : 'text-muted hover:text-ink'}`}>
                {n.label}
                {!!n.badge && <span aria-label={`ждут ответа: ${n.badge}`} className="rounded-full bg-primary px-[7px] py-px text-[11px] font-semibold text-white">{n.badge}</span>}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex flex-wrap items-center gap-3">
            <LinkButton to="/help" variant="secondary" size="sm" title="Как это работает" aria-label="Как это работает">?</LinkButton>
            {personas.data && personas.data.length > 0 && <DemoSwitch personas={personas.data} me={me} onSwitch={(id) => void switchTo(id)} />}
            {me && <NotificationsBell />}
            {me
              ? <ProfileMenu me={me} onLogout={() => void run(async () => { await logout(); nav('/') })} />
              : !isLoading && !bleed && <LinkButton to="/login" variant="secondary" size="sm">Войти</LinkButton>}
          </div>
        </div>
      </header>
      {error && <p role="alert" className="bg-danger-soft px-6 py-2 text-sm text-danger">{error}</p>}
      <main className={bleed ? 'flex-1' : 'mx-auto w-full max-w-[1240px] flex-1'}><FocusModeContext.Provider value={setFocus}><Outlet /></FocusModeContext.Provider></main>
    </div>
  )
}
