import { describe, expect, it } from 'vitest'
import { housingName, housingOptions } from './housing'

describe('housing choices on the contract screen', () => {
  it('shows only the two current choices while keeping the API codes', () => {
    const options = housingOptions({ housing_types: [
      { code: 'detached_multiunit', name: '원룸·다가구', description: '' },
      { code: 'officetel', name: '오피스텔', description: '' },
      { code: 'multifamily', name: '빌라', description: '' },
      { code: 'apartment', name: '아파트', description: '' },
    ] })
    expect(options).toEqual([
      { code: 'detached_multiunit', name: '원룸·투룸·빌라' },
      { code: 'officetel', name: '오피스텔' },
    ])
    expect(options[0].code).toBe('detached_multiunit')
    expect(housingName('detached_multiunit')).toBe('원룸·투룸·빌라')
    expect(housingName('officetel')).toBe('오피스텔')
  })
})
