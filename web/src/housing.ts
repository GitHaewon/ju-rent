import type { Meta } from './types'

const DISPLAY_HOUSING = [
  { code: 'oneroom', name: '원룸·투룸·빌라' },
  { code: 'officetel', name: '오피스텔' },
  { code: 'apartment', name: '아파트' },
] as const

export function housingOptions(meta: Pick<Meta, 'housing_types'>) {
  return DISPLAY_HOUSING.filter(option => meta.housing_types.some(kind => kind.code === option.code))
}

export function housingName(code: string): string {
  return DISPLAY_HOUSING.find(option => option.code === code)?.name ?? ''
}

export function areaBounds(code: string): { min: number; max: number } {
  return code === 'apartment' ? { min: 40, max: 132 } : { min: 15, max: 45 }
}

export function clampArea(area: number, code: string): number {
  const { min, max } = areaBounds(code)
  return Math.min(max, Math.max(min, area))
}
