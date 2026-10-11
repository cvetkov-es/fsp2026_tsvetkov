import type { ReactNode } from 'react'
import type { Cell, Prompt } from '../../api/assessment'
import { Input } from '../ui'
import { INPUT_CLASS_TITLES, type VerdictValue } from './verdict'

const VERDICTS = [['ok', 'Верно'], ['defect', 'Неверно'], ['clarify', 'Нужно уточнить требование']] as const

function Radio({ name, checked, onChange, children }: { name: string; checked: boolean; onChange: () => void; children: ReactNode }) {
  return (
    <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-line px-3 py-1.5 hover:bg-surface-2">
      <input type="radio" name={name} checked={checked} onChange={onChange} />{children}
    </label>
  )
}

function DataEditor({ prompt, rows, maxRows, onChange }: {
  prompt: Prompt; rows: Record<string, Cell[][]>; maxRows: number; onChange: (rows: Record<string, Cell[][]>) => void
}) {
  const total = Object.values(rows).reduce((n, r) => n + r.length, 0)
  return (
    <div className="space-y-3">
      {prompt.tables.map((t) => {
        const data = rows[t.name] ?? []
        const setCell = (r: number, c: number, val: string) =>
          onChange({ ...rows, [t.name]: data.map((row, i) => (i === r ? row.map((x, j) => (j === c ? val : x)) : row)) })
        return (
          <div key={t.name}>
            <p className="font-mono text-sm text-primary">{t.name}</p>
            <table className="font-mono text-sm">
              <thead><tr>{t.columns.map((c) => <th key={c} className="px-1 text-left">{c}</th>)}<th /></tr></thead>
              <tbody>{data.map((row, r) => (
                <tr key={r}>
                  {t.columns.map((c, j) => (
                    <td key={c} className="p-1"><Input aria-label={`${t.name}: строка ${r + 1}, ${c}`} maxLength={40} value={String(row[j] ?? '')} onChange={(e) => setCell(r, j, e.target.value)} /></td>
                  ))}
                  <td><button type="button" className="text-xs text-primary hover:text-primary-hover" onClick={() => onChange({ ...rows, [t.name]: data.filter((_, i) => i !== r) })}>убрать</button></td>
                </tr>
              ))}</tbody>
            </table>
            <button type="button" disabled={total >= maxRows} className="text-sm text-primary hover:text-primary-hover disabled:opacity-40"
              onClick={() => onChange({ ...rows, [t.name]: [...data, t.columns.map(() => '')] })}>+ строка в {t.name}</button>
          </div>
        )
      })}
      <p className="text-xs text-muted">Пустая ячейка или NULL означают NULL. Дробную часть отделяйте точкой или запятой (1,5 = 1.5), без разделителей тысяч. Всего не больше {maxRows} строк.</p>
    </div>
  )
}

/** Ответ на вердикт «Работы с ИИ»: одинаковый вид для любого задания, чтобы форма не подсказывала ответ. */
export function VerdictInput({ prompt, value, onChange, maxRows }: {
  prompt: Prompt; value: unknown; onChange: (v: VerdictValue) => void; maxRows: number
}) {
  const v = (value && typeof value === 'object' ? value : {}) as VerdictValue
  const set = (patch: Partial<VerdictValue>) => onChange({ ...v, ...patch })
  const lines = (prompt.code ?? '').split('\n').length
  return (
    <div className="space-y-4">
      <fieldset className="space-y-1">
        <legend className="mb-1 font-semibold text-ink">Ваш ответ</legend>
        {VERDICTS.map(([k, title]) => <Radio key={k} name="verdict" checked={v.verdict === k} onChange={() => set({ verdict: k })}>{title}</Radio>)}
      </fieldset>
      {v.verdict === 'defect' && (
        <div className="space-y-3 rounded-xl bg-surface-2 p-3">
          <label className="flex items-center gap-2">Строка с ошибкой
            <select className="rounded-lg border border-line-strong px-2 py-1" value={v.line ?? ''} onChange={(e) => set({ line: Number(e.target.value) })}>
              <option value="" disabled>—</option>
              {Array.from({ length: lines }, (_, i) => <option key={i} value={i + 1}>{i + 1}</option>)}
            </select>
          </label>
          {prompt.language === 'sql' ? (
            <div>
              <p className="mb-1 font-semibold text-ink">Данные, на которых решение ошибается</p>
              <DataEditor prompt={prompt} rows={v.rows ?? {}} maxRows={maxRows} onChange={(rows) => set({ rows })} />
            </div>
          ) : (
            <fieldset className="space-y-1">
              <legend className="mb-1 font-semibold text-ink">Ломающий вход</legend>
              <p className="mb-1 text-xs text-muted">Выберите, какой вход ломает решение: например, пустой список или значение ровно на границе.</p>
              {(prompt.input_classes ?? []).map((c) => (
                <Radio key={c} name="input_class" checked={v.input_class === c} onChange={() => set({ input_class: c })}>{INPUT_CLASS_TITLES[c] ?? c}</Radio>
              ))}
            </fieldset>
          )}
        </div>
      )}
      {v.verdict === 'clarify' && (
        <fieldset className="space-y-1 rounded-xl bg-surface-2 p-3">
          <legend className="mb-1 font-semibold text-ink">Что уточнить</legend>
          {(prompt.clarify ?? []).map((o, i) => <Radio key={i} name="clarify" checked={v.clarify === i} onChange={() => set({ clarify: i })}>{o}</Radio>)}
        </fieldset>
      )}
      <fieldset>
        <legend className="mb-1 font-semibold text-ink">Уверенность</legend>
        <div className="flex gap-3">
          <Radio name="confidence" checked={v.confidence === 'low'} onChange={() => set({ confidence: 'low' })}>Низкая</Radio>
          <Radio name="confidence" checked={v.confidence === 'high'} onChange={() => set({ confidence: 'high' })}>Высокая</Radio>
        </div>
      </fieldset>
    </div>
  )
}
