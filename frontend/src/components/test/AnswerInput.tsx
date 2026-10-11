import type { AnswerKind, Cell, Prompt } from '../../api/assessment'
import { Input, Textarea } from '../ui'
import { VerdictInput } from './VerdictInput'

type Props = { kind: AnswerKind; prompt: Prompt; value: unknown; onChange: (v: unknown) => void; maxRows?: number }
const KEYS = 'ABCDEFGH'
const ACTION = 'text-sm font-medium text-primary hover:text-primary-hover'

export function AnswerInput({ kind, prompt, value, onChange, maxRows = 20 }: Props) {
  if (kind === 'verdict') return <VerdictInput prompt={prompt} value={value} onChange={onChange} maxRows={maxRows} />
  if (kind === 'choice') {
    const options = prompt.options ?? []
    const short = options.every((o) => o.length <= 24)  // короткие значения — плиткой в две колонки, как в макете
    return (
      <fieldset className={`grid gap-2.5 ${short ? 'sm:grid-cols-2' : ''}`}>
        <legend className="sr-only">Варианты ответа</legend>
        {options.map((o, i) => (
          <label key={i} data-key={KEYS[i] ?? ''}
            className="flex cursor-pointer items-center gap-3 rounded-xl border-[1.5px] border-line bg-white px-4 py-3.5 text-[15px] font-medium transition before:grid before:size-[26px] before:shrink-0 before:place-items-center before:rounded-[7px] before:bg-canvas before:text-xs before:font-semibold before:text-muted before:content-[attr(data-key)] hover:border-primary-line has-checked:border-primary has-checked:bg-primary-tint has-checked:before:bg-primary has-checked:before:text-white has-focus-visible:outline-2 has-focus-visible:outline-primary">
            <input type="radio" name="choice" className="sr-only" checked={value === i} onChange={() => onChange(i)} />
            <span className={short ? 'font-mono' : ''}>{o}</span>
          </label>
        ))}
      </fieldset>
    )
  }
  if (kind === 'order') {
    const seq = Array.isArray(value) ? (value as number[]) : []
    return (
      <div className="space-y-2">
        <ol className="space-y-2">
          {(prompt.steps ?? []).map((s, i) => {
            const pos = seq.indexOf(i + 1)
            return (
              <li key={i}>
                <button type="button" disabled={pos >= 0} onClick={() => onChange([...seq, i + 1])}
                  className="flex w-full items-start gap-3 rounded-xl border-[1.5px] border-line bg-white px-4 py-3 text-left transition hover:border-primary-line disabled:border-primary disabled:bg-primary-tint">
                  <span className={`grid size-[26px] shrink-0 place-items-center rounded-[7px] text-xs font-semibold ${pos >= 0 ? 'bg-primary text-white' : 'bg-canvas text-muted'}`}>{pos >= 0 ? pos + 1 : '·'}</span>
                  <span>{i + 1}. {s}</span>
                </button>
              </li>
            )
          })}
        </ol>
        <button type="button" className={ACTION} onClick={() => onChange([])}>Сбросить порядок</button>
      </div>
    )
  }
  if (kind === 'rows') {
    const rows = Array.isArray(value) ? (value as Cell[][]) : [['']]
    const set = (r: number, c: number, v: string) => onChange(rows.map((row, i) => (i === r ? row.map((x, j) => (j === c ? v : x)) : row)))
    const cols = Math.max(1, ...rows.map((r) => r.length))
    return (
      <div className="space-y-2">
        <div className="overflow-x-auto"><table className="font-mono text-sm"><tbody>{rows.map((row, r) => (
          <tr key={r}>{Array.from({ length: cols }, (_, c) => (
            <td key={c} className="p-1"><Input className="font-mono" aria-label={`ячейка ${r + 1}-${c + 1}`} value={String(row[c] ?? '')} onChange={(e) => set(r, c, e.target.value)} /></td>
          ))}</tr>
        ))}</tbody></table></div>
        <div className="flex gap-4">
          <button type="button" className={ACTION} onClick={() => onChange([...rows, Array(cols).fill('')])}>+ строка</button>
          <button type="button" className={ACTION} onClick={() => onChange(rows.map((r) => [...r, '']))}>+ столбец</button>
        </div>
      </div>
    )
  }
  if (kind === 'text') {
    return <Textarea className="font-mono" rows={3} value={typeof value === 'string' ? value : ''} onChange={(e) => onChange(e.target.value)} />
  }
  return <Input className="max-w-xs font-mono text-lg!" inputMode={kind === 'line' ? 'numeric' : 'decimal'} value={typeof value === 'string' ? value : ''}
    onChange={(e) => onChange(e.target.value)} />
}
