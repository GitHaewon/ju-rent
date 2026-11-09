import { describe, expect, it } from 'vitest'
import { axisTicks, pinPlacement, shouldDrawDistribution } from './distribution'

describe('distribution presentation', () => {
  it('hides all plotted elements when judgment is on hold', () => {
    expect(shouldDrawDistribution('표본 부족', 20)).toBe(false)
    expect(shouldDrawDistribution('보통', 20)).toBe(true)
  })

  it('pins values outside observed transactions to the appropriate edge', () => {
    expect(pinPlacement(37, 46, 47, 30, 50))
      .toEqual({ position: 0, tag: '비교한 거래보다 싸요', edge: 'low' })
    expect(pinPlacement(75, 11, 70, 0, 90))
      .toEqual({ position: 100, tag: '비교한 거래보다 비싸요', edge: 'high' })
    expect(pinPlacement(46.5, 46, 47, 30, 50))
      .toEqual({ position: 82.5, tag: '이 방', edge: null })
  })

  it('makes three or four unique 10-man-won axis ticks even for narrow ranges', () => {
    for (const [low, high] of [[46, 47], [11, 70], [0, 1], [95, 105]]) {
      const ticks = axisTicks(low, high)
      expect(ticks.length).toBeGreaterThanOrEqual(3)
      expect(ticks.length).toBeLessThanOrEqual(4)
      expect(new Set(ticks).size).toBe(ticks.length)
      expect(ticks.every(tick => Number.isInteger(tick) && tick % 10 === 0)).toBe(true)
      expect(ticks[0]).toBeLessThanOrEqual(low)
      expect(ticks.at(-1)).toBeGreaterThanOrEqual(high)
    }
  })
})
