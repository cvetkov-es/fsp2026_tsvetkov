import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { NdcgChart } from '../components/lab/Charts'

describe('NdcgChart', () => {
  it('puts the value after the confidence whisker and names ablations in Russian', () => {
    const { container } = render(<NdcgChart bars={[
      { key: 'ours', title: 'Наше ранжирование', mean: 0.66, ci_low: 0.61, ci_high: 0.72, group: 'ranker' },
      { key: 'no_fsp', title: 'без ФСП', mean: 0.65, ci_low: 0.6, ci_high: 0.7, group: 'ablation' },
    ]} />)
    expect(screen.getByText('Наше без ФСП')).toBeInTheDocument()
    const whisker = container.querySelector('line')!
    const label = screen.getByText('0.66')
    expect(Number(label.getAttribute('x'))).toBeGreaterThan(Number(whisker.getAttribute('x2')))
  })
})
