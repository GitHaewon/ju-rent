import { describe, expect, it } from 'vitest'
import { EMPTY_BUDGET_MESSAGE, ageBandLabel, availabilityTone, budgetSummary, cardToContract, integerMoney, tenDealSentence, typicalArea, typicalRange, typicalTerms } from './areaCopy'
import type { BudgetRecommendation } from './types'

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
})
