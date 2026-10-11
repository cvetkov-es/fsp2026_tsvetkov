import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Timer } from '../components/test/Timer'

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

describe('Timer', () => {
  it('counts down and fires onExpire exactly once', () => {
    const onExpire = vi.fn()
    render(<Timer seconds={3} onExpire={onExpire} />)
    expect(screen.getByText('0:03')).toBeInTheDocument()
    act(() => { vi.advanceTimersByTime(3100) })
    act(() => { vi.advanceTimersByTime(3000) })
    expect(onExpire).toHaveBeenCalledTimes(1)
  })
})

describe('Timer with changing onExpire', () => {
  it('does not restart when parent passes a new callback (re-render on typing)', () => {
    const first = vi.fn()
    const second = vi.fn()
    const { rerender } = render(<Timer seconds={5} onExpire={first} />)
    act(() => { vi.advanceTimersByTime(3000) })
    rerender(<Timer seconds={5} onExpire={second} />)
    expect(screen.getByText('0:02')).toBeInTheDocument()
    act(() => { vi.advanceTimersByTime(2100) })
    expect(first).not.toHaveBeenCalled()
    expect(second).toHaveBeenCalledTimes(1)
  })
})
