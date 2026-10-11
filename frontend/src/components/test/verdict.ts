/** Ответ на вердикт «Работы с ИИ»: типы и проверки отдельно от компонента (быстрое обновление Vite). */

import type { Cell } from '../../api/assessment'

/** Закрытый список классов ломающего входа (процесс 2.5) — как INPUT_CLASSES на бэкенде. */
export const INPUT_CLASS_TITLES: Record<string, string> = {
  empty: 'Пустой ввод', none: 'None или NULL', dup: 'Дубликаты', negative: 'Отрицательное число',
  boundary: 'Граница диапазона', unicode: 'Юникод',
}

export type VerdictValue = {
  verdict?: 'ok' | 'defect' | 'clarify'; confidence?: 'low' | 'high'; line?: number
  input_class?: string; rows?: Record<string, Cell[][]>; clarify?: number
}

/** Отправить можно, когда ответ полный: вердикт, уверенность, а для «неверно» — строка и ломающий вход,
 * для «уточнить» — вопрос. Иначе балл потерялся бы молча; верен ли ответ — проверит сервер. */
export const verdictReady = (v: unknown) => {
  const x = (v ?? {}) as VerdictValue
  if (!x.verdict || !x.confidence) return false
  if (x.verdict === 'defect') return !!x.line && (!!x.input_class || Object.values(x.rows ?? {}).some((r) => r.length > 0))
  if (x.verdict === 'clarify') return x.clarify !== undefined
  return true
}
