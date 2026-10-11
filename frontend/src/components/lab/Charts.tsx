import type { NdcgBar, OcPoint } from '../../api/lab'

const W = 560, H = 260, PAD = 40

/** График 1: вероятность подтверждения в зависимости от расстояния до порога (простой SVG без зависимостей). */
export function OcChart({ points }: { points: OcPoint[] }) {
  const xs = points.map((p) => p.delta)
  const x = (d: number) => PAD + ((d - xs[0]) / (xs[xs.length - 1] - xs[0])) * (W - 2 * PAD)
  const y = (v: number) => H - PAD - v * (H - 2 * PAD)
  const line = (key: keyof Omit<OcPoint, 'delta'>) => points.map((p, i) => `${i ? 'L' : 'M'}${x(p.delta).toFixed(1)},${y(p[key]).toFixed(1)}`).join(' ')
  const series: [keyof Omit<OcPoint, 'delta'>, string, string, string, string?][] = [
    ['full', 'Полный тест: подтверждён', 'stroke-ink', 'bg-ink'],
    ['express_confirmed', 'Экспресс: подтверждён', 'stroke-primary', 'bg-primary'],
    ['express_undecided', 'Экспресс: нужно продолжить', 'stroke-primary-mist', 'bg-primary-mist', '5 4'],
  ]
  return (
    <figure>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Кривая решений теста" className="w-full">
        <line x1={PAD} y1={H - PAD} x2={W - PAD} y2={H - PAD} className="stroke-line" />
        <line x1={x(0)} y1={PAD / 2} x2={x(0)} y2={H - PAD} className="stroke-line" strokeDasharray="3 3" />
        {[0, 0.5, 1].map((v) => <text key={v} x={8} y={y(v) + 4} fontSize="11" className="fill-subtle">{v * 100}%</text>)}
        {[-2, -1, 0, 1, 2].map((d) => <text key={d} x={x(d) - 6} y={H - PAD + 16} fontSize="11" className="fill-subtle">{d}</text>)}
        {series.map(([k, , stroke, , dash]) => <path key={k} d={line(k)} className={stroke} fill="none" strokeWidth={2.5} strokeDasharray={dash} />)}
      </svg>
      <figcaption className="mt-1 flex flex-wrap gap-4 text-xs">
        {series.map(([k, title, , swatch]) => <span key={k} className="flex items-center gap-1"><span className={`inline-block h-1 w-5 ${swatch}`} />{title}</span>)}
        <span className="text-muted">по оси X: θ минус порог Middle, в логитах</span>
      </figcaption>
    </figure>
  )
}

/** График 2: nDCG@10 нашего ранжирования, бейзлайнов и ablation с 95% доверительными интервалами. */
export function NdcgChart({ bars }: { bars: NdcgBar[] }) {
  const rowH = 24, left = 190, width = W - left - 20
  const h = bars.length * rowH + 20
  return (
    <svg viewBox={`0 0 ${W} ${h}`} role="img" aria-label="nDCG@10 по ранжировщикам" className="w-full">
      {bars.map((b, i) => {
        const yy = 10 + i * rowH
        const mean = b.mean ?? 0
        const labelX = left + Math.max(mean, b.ci_high ?? 0) * width + 6  // подпись — за усом интервала, а не поверх него
        const fill = b.key === 'ours' ? 'fill-primary' : b.group === 'ranker' ? 'fill-ink' : 'fill-primary-mist'
        return (
          <g key={b.key}>
            <text x={left - 8} y={yy + 15} fontSize="12" textAnchor="end" className="fill-ink">{b.group === 'ablation' ? `Наше ${b.title}` : b.title}</text>
            <rect x={left} y={yy + 4} width={Math.max(1, mean * width)} height={rowH - 8} className={fill} rx={3} />
            {b.ci_low != null && b.ci_high != null && <line x1={left + b.ci_low * width} x2={left + b.ci_high * width} y1={yy + rowH / 2} y2={yy + rowH / 2} className="stroke-ink" />}
            <text x={labelX} y={yy + 15} fontSize="11" className="fill-ink">{b.mean == null ? '—' : b.mean.toFixed(2)}</text>
          </g>
        )
      })}
    </svg>
  )
}
