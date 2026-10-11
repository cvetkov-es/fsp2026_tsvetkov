import { copyGuard } from './copy-guard'
import type { Prompt } from '../../api/assessment'

export function PromptText({ text }: { text: string }) {
  return <h1 className="whitespace-pre-wrap text-xl font-semibold leading-snug tracking-[-0.02em] text-pretty sm:text-2xl">{text}</h1>
}

export function PromptTables({ tables }: { tables: Prompt['tables'] }) {
  return (
    <>
      {tables.map((t) => (
        <div key={t.name}>
          <p className="mb-2 font-mono text-[13px] text-muted">{t.name}</p>
          <div className="overflow-x-auto rounded-xl border border-line">
            <table className="w-full border-collapse font-mono text-[13px]">
              <thead className="bg-surface-2"><tr>{t.columns.map((c) => <th key={c} className="border-b border-line px-3.5 py-2 text-left text-xs font-semibold text-muted">{c}</th>)}</tr></thead>
              <tbody>{t.rows.map((r, i) => (
                <tr key={i} className="border-t border-line-soft first:border-t-0">
                  {r.map((v, j) => <td key={j} className="px-3.5 py-2">{v === null ? <span className="text-subtle">NULL</span> : String(v)}</td>)}
                </tr>
              ))}</tbody>
            </table>
          </div>
        </div>
      ))}
    </>
  )
}

/** numbered — номера строк (вердикты «Работы с ИИ» ссылаются на строку с ошибкой). */
export function PromptCode({ code, language, numbered = false }: { code: string; language: string | null; numbered?: boolean }) {
  return (
    <pre aria-label={`код ${language ?? ''}`} className={`overflow-x-auto rounded-[14px] bg-ink py-5 pr-5 font-mono text-[13.5px] leading-7 text-code ${numbered ? 'pl-2' : 'pl-5'}`}>
      {numbered
        ? code.split('\n').map((ln, i) => <div key={i} className="flex"><span className="w-9 shrink-0 select-none pr-4 text-right text-night-muted">{i + 1}</span><span>{ln}</span></div>)
        : code}
    </pre>
  )
}

export function PromptHint({ hint }: { hint: string | null }) {
  return hint ? <p className="whitespace-pre-wrap text-sm text-muted">{hint}</p> : null
}

/** Задание целиком в одну колонку (страница теста раскладывает части по двум колонкам сама). */
export function ItemPrompt({ prompt, onCopyAttempt, numbered = false, allowCopy = false }: {
  prompt: Prompt; onCopyAttempt?: () => void; numbered?: boolean; allowCopy?: boolean
}) {
  return (
    <div className="space-y-5" onCopy={copyGuard(allowCopy, onCopyAttempt)}>
      <PromptText text={prompt.text} />
      <PromptTables tables={prompt.tables} />
      {prompt.code && <PromptCode code={prompt.code} language={prompt.language} numbered={numbered} />}
      <PromptHint hint={prompt.answer_hint} />
    </div>
  )
}
