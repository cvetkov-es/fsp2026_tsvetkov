import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

const STEPS = ['Опрос: направление и заявленный грейд', 'Тест подтверждает грейд и навыки', 'Приглашения от компаний']

/** Экран входа из макета (09-login.png): герой на тёмном слева, форма справа; на телефоне — герой коротко сверху. */
export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <div className="grid lg:min-h-[calc(100dvh-4rem)] lg:grid-cols-[1.1fr_1fr]">
      <section className="flex flex-col justify-center gap-10 bg-ink px-6 py-10 text-white sm:px-14 sm:py-14 lg:justify-between">
        <div className="max-w-[520px] lg:mt-16">
          <h1 className="text-3xl font-semibold leading-[1.05] tracking-[-0.035em] text-balance sm:text-5xl lg:text-[52px]">Компании приходят к вам с предложением.</h1>
          <p className="mt-5 hidden text-lg leading-normal text-pretty text-night-text sm:block">
            Подтвердите грейд тестом. Работодатели увидят результат и сами пришлют приглашение с вилкой и следующим шагом. Неудачные попытки работодатели не видят.
          </p>
          <p className="mt-3 hidden text-lg leading-normal text-pretty text-night-text sm:block">
            Работодателю сервис показывает готовые категории кандидатов. Остаётся выбрать человека и отправить приглашение.
          </p>
        </div>
        <ol className="hidden gap-px overflow-hidden rounded-[14px] bg-night-line sm:grid sm:grid-cols-3">
          {STEPS.map((s, i) => (
            <li key={s} className="bg-night-2 p-[18px]">
              <span className="font-mono text-[13px] text-night-accent">0{i + 1}</span>
              <p className="mt-2 text-sm text-night-text">{s}</p>
            </li>
          ))}
        </ol>
      </section>
      <section className="grid place-items-center bg-white px-6 py-12">
        <div className="w-full max-w-[380px]">{children}</div>
      </section>
    </div>
  )
}

export function AuthTabs({ active }: { active: 'login' | 'register' }) {
  const tab = (on: boolean) => `flex-1 rounded-[7px] py-2.5 text-center text-sm font-medium transition ${on ? 'bg-white text-ink shadow-sm' : 'text-muted hover:text-ink'}`
  return (
    <nav aria-label="Вход или регистрация" className="mb-8 flex gap-1 rounded-[10px] bg-canvas p-1">
      <Link to="/login" aria-current={active === 'login' ? 'page' : undefined} className={tab(active === 'login')}>Вход</Link>
      <Link to="/register" aria-current={active === 'register' ? 'page' : undefined} className={tab(active === 'register')}>Регистрация</Link>
    </nav>
  )
}
