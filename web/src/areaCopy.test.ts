import { describe, expect, it } from 'vitest'
import { EMPTY_BUDGET_MESSAGE, ageBandLabel, availabilityTone, budgetSummary, budgetPriceDifference, cardToContract, commuteDetail, commuteLabel, commuteRange, integerMoney, priceDifference, tenDealSentence, typicalArea, typicalRange, typicalTerms } from './areaCopy'
import type { BudgetRecommendation, Meta } from './types'
import { visibleCommuteDongs } from './commuteChoices'

const card: BudgetRecommendation = {
  dong: '효자동2가', housing_type: 'oneroom', age_band: '5~9년', n: 40,
  within_budget_count: 20, within_budget_pct: 50,
  availability_label: '쉽게 구할 수 있어요',
  quantiles_10k_krw: { p25: 30, p50: 35, p75: 40 },
  deposit_median_10k_krw: 500.5, monthly_median_10k_krw: 35.5,
  area_median_sqm: 26.48,
  typical_terms_note: '보증금과 월세 각각의 중간값이며 한 거래의 조건은 아니에요.',
}

describe('budget and comparison screen copy', () => {
  it('keeps the API possibility label and applies its glass badge tone', () => {
    expect(card.availability_label).toBe('쉽게 구할 수 있어요')
    expect(availabilityTone(card.availability_label)).toBe('easy')
    expect(availabilityTone('발품 팔면 가능해요')).toBe('possible')
    expect(tenDealSentence(card)).toBe('비슷한 거래 10건 중 5건이 예산 안')
  })

  it('floors the ten-deal count at the 50% badge boundary', () => {
    expect(tenDealSentence({ within_budget_pct: 49.9 })).toBe('비슷한 거래 10건 중 4건이 예산 안')
    expect(tenDealSentence({ within_budget_pct: 50 })).toBe('비슷한 거래 10건 중 5건이 예산 안')
  })

  it('shows the API area median and explains an unknown building age', () => {
    expect(typicalArea(card.area_median_sqm)).toBe('보통 8.0평(26.5㎡)')
    expect(ageBandLabel('미기재')).toBe('연식 정보 없음')
    expect(ageBandLabel('5~9년')).toBe('5~9년')
  })

  it('keeps contract terms and the usual range in integer ten-thousand won', () => {
    expect(integerMoney(1234.5)).toBe('1,235')
    expect(typicalRange(1234.49, 2345.5)).toBe('보통 1,234~2,346만 원')
  })

  it('uses a student-facing empty message without an internal grouping term', () => {
    expect(budgetSummary(0)).toBe('조건에 맞는 선택지 0개를 찾았어요')
    expect(EMPTY_BUDGET_MESSAGE).toContain('월세 예산을 올리거나 최소 면적을 줄여 보세요')
    expect(EMPTY_BUDGET_MESSAGE).not.toContain('조합')
  })

  it('formats D-042 from separate API medians with integer rounding', () => {
    expect(typicalTerms(card)).toBe('보증금 501만 원, 월세 36만 원 안팎')
    expect(typicalTerms({ deposit_median_10k_krw: 1234.49, monthly_median_10k_krw: 35.49 }))
      .toBe('보증금 1,234만 원, 월세 35만 원 안팎')
  })

  it('fills contract judgment from the selected card and the shared rate', () => {
    expect(cardToContract(card, '효자동권', 5)).toEqual({
      campus: '효자동권', housing_type: 'oneroom', area: 26.48,
      deposit: 501, monthly: 36, construction_year: null, rate_pct: 5,
    })
  })

  it('shows the reviewed minimum to rounded median stop range and missing interval', () => {
    expect(commuteRange(6, 14.5)).toBe('버스 정류장 6~15개')
    expect(commuteRange(5, 5.2)).toBe('버스 정류장 5개')
    const bus = { campus_area: false, campus_adjacent: false, min_stops: 6,
      median_stops: 14.5, boarding_stops: 10, direct_routes: 3, interval_min: null, planned_interval_min: null }
    expect(commuteLabel(bus)).toBe('버스 정류장 6~15개')
    expect(commuteDetail(bus)).toBe('직행 3개 노선')
    expect(commuteDetail({ ...bus, planned_interval_min: 23 })).toBe('직행 3개 노선, 운행계획상 평균 약 23분')
    expect(commuteDetail({ ...bus, campus_area: true })).toBe('')
    expect(commuteLabel({ ...bus, campus_adjacent: true })).toBe('캠퍼스 바로 옆')
    expect(commuteLabel({ ...bus, campus_area: true })).toBe('캠퍼스 주변')
  })

  it('hands off the selected commute dong and school and displays price direction', () => {
    const commute = { campus_area: false, campus_adjacent: false, min_stops: 2,
      median_stops: 5, boarding_stops: 17, direct_routes: 4, interval_min: 16, planned_interval_min: null }
    expect(cardToContract({ ...card, dong: '서신동', commute }, '효자동권', 5, '전주대학교'))
      .toMatchObject({ dong: '서신동', school: '전주대학교' })
    expect(priceDifference(-4.2)).toContain('4만 원 낮아요')
    expect(priceDifference(4.2)).toBe('같은 연식 캠퍼스 주변보다 환산 월세 4만 원 높아요')
    expect(priceDifference(null)).toBe('')
  })
  it('hides the same-age comparison for cards without building age', () => {
    expect(budgetPriceDifference({ age_band: '미기재', campus_price_difference_10k_krw: 4.2 })).toBe('')
    expect(budgetPriceDifference({ age_band: '20년 이상', campus_price_difference_10k_krw: 4.2 }))
      .toBe('같은 연식 캠퍼스 주변보다 환산 월세 4만 원 높아요')
    expect(budgetPriceDifference({ age_band: '20년 이상', campus_price_difference_10k_krw: null })).toBe('')
  })
  it('hides zero-deal dongs and marks fewer than 30 deals for the chosen housing', () => {
    const base = { campus_area: false, campus_adjacent: false, min_stops: 5,
      median_stops: 8, boarding_stops: 1, direct_routes: 1,
      interval_min: null, planned_interval_min: null }
    const fake = {
      commute_by_school: { school: [
        { ...base, dong: '없는동', emd_cd: '1' },
        { ...base, dong: '적은동', emd_cd: '2' },
        { ...base, dong: '충분한동', emd_cd: '3' },
      ] },
      commute_deal_counts_by_school: { school: { oneroom: { 적은동: 29, 충분한동: 30 }, apartment: { 충분한동: 1 } } },
    } as unknown as Meta
    expect(visibleCommuteDongs(fake, 'school', 'oneroom').map(choice => choice.label))
      .toEqual(['적은동 (최근 거래 적음)', '충분한동'])
    expect(visibleCommuteDongs(fake, 'school', 'apartment').map(choice => choice.label))
      .toEqual(['충분한동 (최근 거래 적음)'])
  })
})
