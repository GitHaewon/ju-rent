import { describe, expect, it } from 'vitest'
import { distributionAxis, pinPlacement, positionOnAxis, shouldDrawDistribution } from './distribution'

describe('distribution presentation', () => {
  it('hides all plotted elements when judgment is on hold', () => {
    expect(shouldDrawDistribution('표본 부족', 20)).toBe(false)
    expect(shouldDrawDistribution('판단 보류', 20)).toBe(false)
    expect(shouldDrawDistribution('제공 안 함', 0)).toBe(false)
    expect(shouldDrawDistribution('보통', 20)).toBe(true)
  })

  it('rounds the observed domain outward to 10만 원 and includes the listing', () => {
    expect(distributionAxis(11.25, 70.08, 47.08)).toEqual({ low: 10, high: 80, ticks: [10, 30, 50, 70] })
    expect(distributionAxis(11.25, 70.08, 87.1)).toEqual({ low: 10, high: 90, ticks: [10, 30, 50, 70, 90] })
    expect(distributionAxis(43.33, 79.17, 33.5)).toEqual({ low: 30, high: 80, ticks: [30, 50, 70] })
  })

  it('uses one scale for bars, quantiles, ticks, and the listing pin', () => {
    const axis = distributionAxis(11.25, 70.08, 87.1)
    expect(positionOnAxis(11.25, axis)).toBeCloseTo(1.5625)
    expect(positionOnAxis(50, axis)).toBe(50)
    expect(positionOnAxis(70.08, axis)).toBeCloseTo(75.1)
    const pin = pinPlacement(87.1, 11.25, 70.08, axis)
    expect(pin.position).toBeCloseTo(96.375)
    expect(pin.tag).toBe('비교한 거래보다 비싸요')
    expect(pin.edge).toBe('high')
  })

  it('marks out-of-range values at their true scaled position', () => {
    const axis = distributionAxis(46, 47, 37)
    expect(pinPlacement(37, 46, 47, axis))
      .toEqual({ position: 35, tag: '비교한 거래보다 싸요', edge: 'low' })
    expect(pinPlacement(46.5, 46, 47, axis))
      .toEqual({ position: 82.5, tag: '이 방', edge: null })
  })

  it('uses three to five unique ticks at 10만 or 20만 원 intervals for plottable ranges', () => {
    for (const [low, high, value] of [[11.25, 70.08, 47.08], [43.33, 79.17, 33.5], [95, 105, 100]]) {
      const axis = distributionAxis(low, high, value)
      expect(axis.ticks.length).toBeGreaterThanOrEqual(3)
      expect(axis.ticks.length).toBeLessThanOrEqual(5)
      expect(new Set(axis.ticks).size).toBe(axis.ticks.length)
      expect(axis.ticks.every(tick => Number.isInteger(tick) && tick % 10 === 0)).toBe(true)
      expect(new Set(axis.ticks.slice(1).map((tick, i) => tick - axis.ticks[i])).size).toBe(1)
      expect([10, 20]).toContain(axis.ticks[1] - axis.ticks[0])
      expect(axis.ticks[0]).toBe(axis.low)
      expect(axis.ticks.at(-1)).toBeLessThanOrEqual(axis.high)
    }
  })
})
