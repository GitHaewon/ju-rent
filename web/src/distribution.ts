export function shouldDrawDistribution(label: string, binCount: number): boolean {
  return label !== '표본 부족' && binCount > 0
}

export type DistributionAxis = { low: number; high: number; ticks: number[] }

/** Keep the plotted domain on exact 10만 원 boundaries, including the listing. */
export function distributionAxis(observedLow: number, observedHigh: number, listing: number): DistributionAxis {
  const low = Math.floor(Math.min(observedLow, listing) / 10) * 10
  const high = Math.ceil(Math.max(observedHigh, listing) / 10) * 10
  const span = high - low
  const step = span > 40 ? 20 : 10
  const count = Math.min(5, Math.floor(span / step) + 1)
  return { low, high, ticks: Array.from({ length: count }, (_, index) => low + index * step) }
}

export function positionOnAxis(value: number, axis: Pick<DistributionAxis, 'low' | 'high'>): number {
  return Math.min(100, Math.max(0, (value - axis.low) / (axis.high - axis.low) * 100))
}

export function pinPlacement(
  value: number, observedLow: number, observedHigh: number, axis: DistributionAxis,
): { position: number; tag: string; edge: 'low' | 'high' | null } {
  if (value < observedLow) return { position: positionOnAxis(value, axis), tag: '비교한 거래보다 싸요', edge: 'low' }
  if (value > observedHigh) return { position: positionOnAxis(value, axis), tag: '비교한 거래보다 비싸요', edge: 'high' }
  return { position: positionOnAxis(value, axis), tag: '이 방', edge: null }
}
