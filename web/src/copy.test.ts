import { describe, expect, it } from 'vitest'
import { comparisonSentence, displayWarning, percentileSentence, verdictText } from './copy'

describe('student-facing result text', () => {
  it('uses the response percentile for the 100 rooms sentence', () => {
    expect(percentileSentence({ label: '보통', percentile: 76.9, n: 300 }))
      .toBe('비슷한 방 100곳 중 77곳이 이 방보다 쌌어요.')
  })

  it('describes each expansion from the response step', () => {
    const base = { n: 42, comparison_period: { start: '2024-11-01', end: '2026-10-31' } }
    expect(comparisonSentence({ ...base, step: '기본' })).toContain('면적 ±5㎡')
    expect(comparisonSentence({ ...base, step: '면적 ±10㎡' })).toContain('면적 ±10㎡로 넓혀')
    expect(comparisonSentence({ ...base, step: '기간 확대' })).toContain('2021년부터로 넓혀')
  })

  it('holds judgment when the sample is insufficient', () => {
    expect(verdictText({ label: '표본 부족' })).toBe('판단 보류')
    expect(percentileSentence({ label: '표본 부족', percentile: null, n: 8 }))
      .toContain('비슷한 거래가 8건뿐이라 판단하기 어려워요')
  })

  it('uses mockup warning wording only for known engine messages', () => {
    expect(displayWarning('실거래 자료에는 관리비가 포함되지 않습니다.')).toBe('실거래 자료에는 관리비가 없어요.')
    expect(displayWarning('새 경고')).toBe('새 경고')
  })
})
