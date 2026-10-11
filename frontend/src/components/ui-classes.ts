export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'dark' | 'light' | 'outline-light'
export type ButtonSize = 'sm' | 'md' | 'lg'

const VARIANT: Record<ButtonVariant, string> = {
  primary: 'bg-primary text-white hover:bg-primary-hover',
  secondary: 'border border-line-strong bg-white text-ink hover:bg-canvas',
  ghost: 'text-muted hover:bg-canvas hover:text-ink',
  danger: 'border border-line-strong bg-white text-danger hover:bg-danger-soft',
  dark: 'bg-ink text-white hover:bg-night-3',
  light: 'bg-white text-ink hover:bg-canvas',             // на тёмных и синих панелях
  'outline-light': 'border border-white/40 text-white hover:bg-white/10',
}
const SIZE: Record<ButtonSize, string> = {
  sm: 'rounded-[9px] px-3 py-1.5 text-[13px]',
  md: 'rounded-[10px] px-4 py-2.5 text-sm',
  lg: 'rounded-xl px-6 py-3.5 text-[15px]',
}

/** Классы кнопки — для <button> и для ссылок, которые выглядят как кнопки. */
export const buttonClass = (variant: ButtonVariant = 'primary', size: ButtonSize = 'md') =>
  `inline-flex items-center justify-center gap-2 whitespace-nowrap font-semibold transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-40 ${VARIANT[variant]} ${SIZE[size]}`

/** Ссылка-действие в тексте и карточках: цвет и подчёркивание при наведении. */
export const linkClass = 'font-medium text-primary underline-offset-2 hover:text-primary-hover hover:underline'
