// Проверка текстов интерфейса по правилам docs/ux-writing.md.
// node scripts/copy-check.mjs          — нарушения (код выхода 1, если есть)
// node scripts/copy-check.mjs --list   — все тексты интерфейса по файлам (для редактуры)
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import ts from 'typescript'

const ROOT = new URL('../src/', import.meta.url).pathname
const CYR = /[А-Яа-яЁё]/
// Длинное тире посреди фразы; одиночный «—» как прочерк в пустой ячейке допустим
const DASH = /\S\s—\s\S/
const STOP = [/честн/i, /без санкций/i, /наружу/i, /это и есть/i, /не обещаем/i, /\bлишь\b/i, /\bне просто\b/i]

function files(dir) {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n)
    if (statSync(p).isDirectory()) return p === join(ROOT, 'test') ? [] : files(p)  // тесты не проверяем, а components/test — это интерфейс теста
    return /\.(tsx|ts)$/.test(n) && !/\.test\./.test(n) ? [p] : []
  })
}

function texts(path) {
  const src = ts.createSourceFile(path, readFileSync(path, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const out = []
  // Кириллица — признак пользовательского текста; шаблон с длинным тире между подстановками («${a} — ${b}») тоже текст
  const add = (node, text) => {
    const t = text.replace(/\s+/g, ' ').trim()
    if (CYR.test(t) || (ts.isTemplateExpression(node) && DASH.test(t))) out.push({ line: src.getLineAndCharacterOfPosition(node.getStart()).line + 1, text: t })
  }
  const walk = (node) => {
    if (ts.isImportDeclaration(node)) return
    if (ts.isJsxText(node)) add(node, node.text)
    else if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) add(node, node.text)
    else if (ts.isTemplateExpression(node)) add(node, [node.head.text, ...node.templateSpans.map((s) => `{…}${s.literal.text}`)].join(''))
    ts.forEachChild(node, walk)
  }
  walk(src)
  return out
}

const list = process.argv.includes('--list')
let bad = 0
for (const f of files(ROOT)) {
  const rel = relative(ROOT, f)
  for (const { line, text } of texts(f)) {
    if (list) { console.log(`${rel}:${line}\t${text}`); continue }
    const why = [DASH.test(text) && 'длинное тире посреди фразы', ...STOP.filter((r) => r.test(text)).map((r) => `стоп-слово ${r.source}`)].filter(Boolean)
    if (why.length) { bad++; console.log(`${rel}:${line}  ${why.join(', ')}\n    ${text}`) }
  }
}
if (!list) {
  console.log(bad ? `\nнарушений: ${bad} (правила — docs/ux-writing.md)` : 'тексты интерфейса: нарушений нет')
  process.exit(bad ? 1 : 0)
}
