import type { Meta } from './types'

const DISPLAY_HOUSING = [
  { code: 'detached_multiunit', name: '원룸·투룸·빌라' },
  { code: 'officetel', name: '오피스텔' },
] as const

export function housingOptions(meta: Pick<Meta, 'housing_types'>) {
  return DISPLAY_HOUSING.filter(option => meta.housing_types.some(kind => kind.code === option.code))
}

export function housingName(code: string): string {
  return DISPLAY_HOUSING.find(option => option.code === code)?.name ?? ''
}
