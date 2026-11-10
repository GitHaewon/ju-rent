import { describe, expect, it } from 'vitest'
import { areaBounds, clampArea, housingName, housingOptions } from './housing'

describe('housing choices on the contract screen', () => {
  it('shows the three current choices with the combined API code first', () => {
    const options = housingOptions({ housing_types: [
      { code: 'oneroom', name: '원룸·투룸·빌라', description: '' },
      { code: 'detached_multiunit', name: '원룸·다가구', description: '' },
      { code: 'officetel', name: '오피스텔', description: '' },
      { code: 'multifamily', name: '빌라', description: '' },
      { code: 'apartment', name: '아파트', description: '' },
    ] })
    expect(options).toEqual([
      { code: 'oneroom', name: '원룸·투룸·빌라' },
      { code: 'officetel', name: '오피스텔' },
      { code: 'apartment', name: '아파트' },
    ])
    expect(options[0].code).toBe('oneroom')
    expect(housingName('oneroom')).toBe('원룸·투룸·빌라')
    expect(housingName('officetel')).toBe('오피스텔')
    expect(housingName('apartment')).toBe('아파트')
  })

  it('switches area slider limits and clamps the current value', () => {
    expect(areaBounds('oneroom')).toEqual({ min: 15, max: 45 })
    expect(areaBounds('officetel')).toEqual({ min: 15, max: 45 })
    expect(areaBounds('apartment')).toEqual({ min: 40, max: 132 })
    expect(clampArea(25, 'apartment')).toBe(40)
    expect(clampArea(132, 'oneroom')).toBe(45)
    expect(clampArea(65, 'apartment')).toBe(65)
  })
})
