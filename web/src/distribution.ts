export function shouldDrawDistribution(label: string, binCount: number): boolean {
  return label !== '표본 부족' && binCount > 0
}

/** Three or four distinct tick values, each an integer multiple of 10만 원. */
export function axisTicks(low: number, high: number): number[] {
  const floor = Math.max(0, low)
  const ceiling = Math.max(floor + 1, high)
  for (let step = 10; ; step += 10) {
    let start = Math.floor(floor / step) * step
    let end = Math.ceil(ceiling / step) * step
    if ((end - start) / step + 1 > 4) continue
    if (end - start < 2 * step) {
      if (start >= step) start -= step
      else end += step
    }
    const count = Math.round((end - start) / step) + 1
    return Array.from({ length: count }, (_, index) => start + index * step)
  }
}

export function pinPlacement(
  value: number, observedLow: number, observedHigh: number, axisLow: number, axisHigh: number,
): { position: number; tag: string; edge: 'low' | 'high' | null } {
  if (value < observedLow) return { position: 0, tag: '비교한 거래보다 싸요', edge: 'low' }
  if (value > observedHigh) return { position: 100, tag: '비교한 거래보다 비싸요', edge: 'high' }
  return {
    position: Math.min(100, Math.max(0, (value - axisLow) / (axisHigh - axisLow) * 100)),
    tag: '이 방', edge: null,
  }
}
