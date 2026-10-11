import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react'
import { Link, type LinkProps } from 'react-router-dom'
import { buttonClass, type ButtonSize, type ButtonVariant } from './ui-classes'

type Look = { variant?: ButtonVariant; size?: ButtonSize }

export function Button({ variant, size, className = '', ...p }: ButtonHTMLAttributes<HTMLButtonElement> & Look) {
  return <button className={`${buttonClass(variant, size)} ${className}`} {...p} />
}

export function LinkButton({ variant, size, className = '', ...p }: LinkProps & Look) {
  return <Link className={`${buttonClass(variant, size)} ${className}`} {...p} />
}

export type CardTone = 'default' | 'night' | 'primary' | 'tint' | 'success'
const CARD: Record<CardTone, string> = {
  default: 'border border-line bg-white',
  night: 'bg-ink text-white',
  primary: 'bg-primary text-white',
  tint: 'border border-primary-line bg-primary-tint',
  success: 'border border-success-line bg-success-tint',
}

export function Card({ children, className = '', tone = 'default', as: Tag = 'div' }: {
  children: ReactNode; className?: string; tone?: CardTone; as?: 'div' | 'section' | 'article' | 'aside'
}) {
  return <Tag className={`rounded-card p-6 ${CARD[tone]} ${className}`}>{children}</Tag>
}

const FIELD = 'w-full rounded-[10px] border border-line-strong bg-white px-3.5 py-2.5 text-[15px] text-ink outline-none transition placeholder:text-subtle focus:border-primary focus:ring-3 focus:ring-primary-soft disabled:bg-surface-2'

export function Input({ className = '', ...p }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`${FIELD} ${className}`} {...p} />
}

export function Textarea({ className = '', ...p }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={`${FIELD} ${className}`} {...p} />
}

export function Select({ className = '', ...p }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={`${FIELD} pr-8 ${className}`} {...p} />
}

export function Field({ label, htmlFor, hint, children }: { label: string; htmlFor: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={htmlFor} className="text-[13px] font-medium text-ink-2">{label}</label>
      {children}
      {hint && <p className="text-xs text-muted">{hint}</p>}
    </div>
  )
}

export type PillTone = 'neutral' | 'primary' | 'solid' | 'success' | 'danger' | 'warning' | 'dark'
const PILL: Record<PillTone, string> = {
  neutral: 'bg-line-soft text-muted',
  primary: 'bg-primary-soft text-primary-hover',
  solid: 'bg-primary text-white',
  success: 'bg-success-soft text-success',
  danger: 'bg-danger-soft text-danger',
  warning: 'bg-warning-soft text-warning',
  dark: 'bg-ink text-white',
}

export function Pill({ tone = 'neutral', className = '', title, children }: { tone?: PillTone; className?: string; title?: string; children: ReactNode }) {
  return <span title={title} className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ${PILL[tone]} ${className}`}>{children}</span>
}

/** Технология стека: подтверждённая — тёмная с ✓, заявленная — контурная. */
export function TechChip({ tech, confirmed, declaredLabel = false }: { tech: string; confirmed: boolean; declaredLabel?: boolean }) {
  return (
    <span className={`rounded-[7px] border px-2 py-0.5 font-mono text-xs ${confirmed ? 'border-ink bg-ink text-white' : 'border-line bg-white text-muted'}`}>
      {tech}{confirmed ? ' ✓' : declaredLabel ? ' · заявлено' : ''}
    </span>
  )
}

/** Чип фильтра: переключатель с aria-pressed. */
/** active не передан — обычная кнопка-подсказка без состояния. */
export function Chip({ active, className = '', ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { active?: boolean }) {
  return (
    <button type="button" aria-pressed={active}
      className={`rounded-full border px-3.5 py-1.5 text-[13px] font-medium transition ${active ? 'border-ink bg-ink text-white' : 'border-line-strong bg-white text-ink-2 hover:border-ink-2'} ${className}`} {...p} />
  )
}

export function Segmented<T extends string>({ label, options, value, onChange }: {
  label: string; options: { value: T; label: string }[]; value: T | null; onChange: (v: T) => void
}) {
  return (
    <div role="group" aria-label={label} className="flex gap-0.5 rounded-[10px] bg-canvas p-1">
      {options.map((o) => (
        <button key={o.value} type="button" aria-pressed={value === o.value} onClick={() => onChange(o.value)}
          className={`flex-1 rounded-[7px] px-3 py-2 text-sm font-medium transition ${value === o.value ? 'bg-white text-ink shadow-sm' : 'text-muted hover:text-ink'}`}>
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function BackLink({ to, children }: { to: string; children: ReactNode }) {
  return <Link to={to} className="text-sm text-muted hover:text-ink">← {children}</Link>
}

export function PageHeader({ eyebrow, title, description, actions, back }: {
  eyebrow?: ReactNode; title: ReactNode; description?: ReactNode; actions?: ReactNode; back?: ReactNode
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0 flex-[1_1_420px]">
        {back && <div className="mb-2">{back}</div>}
        {eyebrow && <p className="text-sm text-muted">{eyebrow}</p>}
        <h1 className="mt-1.5 text-3xl font-semibold leading-tight tracking-[-0.03em] text-balance sm:text-4xl">{title}</h1>
        {description && <p className="mt-2.5 max-w-[720px] text-[15px] leading-relaxed text-pretty text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

/** Контейнер страницы: поля 16/24 px, узкий вариант — для итогов и форм. */
export function Page({ children, narrow = false, className = '' }: { children: ReactNode; narrow?: boolean; className?: string }) {
  return <div className={`mx-auto w-full space-y-6 px-4 pb-20 pt-8 sm:px-6 sm:pt-10 ${narrow ? 'max-w-[808px]' : 'max-w-[1240px]'} ${className}`}>{children}</div>
}

type NoticeTone = 'neutral' | 'info' | 'warning' | 'danger' | 'success'
const NOTICE: Record<NoticeTone, string> = {
  neutral: 'bg-surface-2 text-ink-2',
  info: 'bg-primary-soft text-primary-hover',
  warning: 'bg-warning-soft text-warning',
  danger: 'bg-danger-soft text-danger',
  success: 'bg-success-soft text-success',
}

export function Notice({ tone = 'neutral', role, className = '', children }: { tone?: NoticeTone; role?: 'alert' | 'status'; className?: string; children: ReactNode }) {
  return <div role={role} className={`rounded-xl px-4 py-3 text-sm leading-relaxed ${NOTICE[tone]} ${className}`}>{children}</div>
}

export function ErrorText({ children, className = '' }: { children?: ReactNode; className?: string }) {
  if (!children) return null
  return <p role="alert" className={`text-sm text-danger ${className}`}>{children}</p>
}

export function Meter({ value, label, tone = 'primary' }: { value: number; label: string; tone?: 'primary' | 'success' }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100)
  return (
    <div role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} className="h-2.5 overflow-hidden rounded-full bg-line-soft">
      <div className={`h-full rounded-full ${tone === 'success' ? 'bg-success-dot' : 'bg-primary'}`} style={{ width: `${pct}%` }} />
    </div>
  )
}

export function StatGrid({ children }: { children: ReactNode }) {
  return <div className="grid gap-px overflow-hidden rounded-[14px] border border-line bg-line sm:grid-cols-3">{children}</div>
}

export function Stat({ label, value }: { label: string; value: ReactNode }) {
  return <div className="bg-white p-4"><p className="text-xs text-muted">{label}</p><p className="mt-1 text-[22px] font-semibold">{value}</p></div>
}

export function Dot({ tone = 'neutral' }: { tone?: 'neutral' | 'success' | 'primary' }) {
  const c = { neutral: 'bg-line-strong', success: 'bg-success-dot', primary: 'bg-primary' }[tone]
  return <span aria-hidden="true" className={`inline-block size-2.5 shrink-0 rounded-full ${c}`} />
}

export function Logo() {
  return <span aria-hidden="true" className="grid size-7 place-items-center rounded-lg bg-primary text-[11px] font-bold tracking-[0.02em] text-white">ФСП</span>
}
