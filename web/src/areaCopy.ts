import type { BudgetRecommendation, ContractInput } from './types'

export const EMPTY_BUDGET_MESSAGE = '이 예산으로는 맞는 집이 적어요. 월세 예산을 올리거나 최소 면적을 줄여 보세요.'

export function budgetSummary(count: number): string {
  return `조건에 맞는 선택지 ${count.toLocaleString('ko-KR')}개를 찾았어요`
}

export function availabilityTone(label: string): 'easy' | 'possible' {
  return label === '쉽게 구할 수 있어요' ? 'easy' : 'possible'
}

export function typicalTerms(card: Pick<BudgetRecommendation, 'deposit_median_10k_krw' | 'monthly_median_10k_krw'>): string {
  const deposit = Math.round(card.deposit_median_10k_krw).toLocaleString('ko-KR')
  const monthly = Math.round(card.monthly_median_10k_krw).toLocaleString('ko-KR')
  return `보증금 ${deposit}만 원, 월세 ${monthly}만 원 안팎`
}

export function tenDealSentence(card: Pick<BudgetRecommendation, 'within_budget_pct'>): string {
  return `비슷한 거래 10건 중 ${Math.floor(card.within_budget_pct / 10)}건이 예산 안`
}

export function typicalArea(areaSqm: number): string {
  return `보통 ${(areaSqm / 3.305785).toFixed(1)}평(${areaSqm.toLocaleString('ko-KR', { maximumFractionDigits: 1 })}㎡)`
}

export function ageBandLabel(ageBand: string): string {
  return ageBand === '미기재' ? '연식 정보 없음' : ageBand
}

export function integerMoney(value: number): string {
  return Math.round(value).toLocaleString('ko-KR')
}

export function typicalRange(p25: number, p75: number): string {
  return `보통 ${integerMoney(p25)}~${integerMoney(p75)}만 원`
}

export function commuteRange(minimum: number, median: number): string {
  const rounded = Math.round(median)
  return `버스 정류장 ${minimum === rounded ? minimum : `${minimum}~${rounded}`}개`
}

export function commuteLabel(commute: NonNullable<BudgetRecommendation['commute']>): string {
  if (commute.campus_area) return '캠퍼스 주변'
  if (commute.campus_adjacent) return '캠퍼스 바로 옆'
  return commuteRange(commute.min_stops!, commute.median_stops!)
}

export function commuteDetail(commute: NonNullable<BudgetRecommendation['commute']>): string {
  if (commute.campus_area) return ''
  const route = `직행 ${commute.direct_routes}개 노선`
  if (commute.interval_min !== null) return `${route}, 가장 자주 오는 버스 ${commute.interval_min}분마다`
  if (commute.planned_interval_min !== null) return `${route}, 운행계획상 평균 약 ${commute.planned_interval_min}분`
  return route
}

export function priceDifference(value: number | null | undefined): string {
  if (value === null || value === undefined) return ''
  const amount = Math.round(Math.abs(value))
  if (amount === 0) return '같은 연식 캠퍼스 주변과 환산 월세가 비슷해요'
  return `같은 연식 캠퍼스 주변보다 환산 월세 ${amount}만 원 ${value < 0 ? '낮아요' : '높아요'}`
}

export function cardToContract(card: BudgetRecommendation, campus: string, rate_pct: number, school?: string): ContractInput {
  const values: ContractInput = {
    campus, housing_type: card.housing_type, area: card.area_median_sqm,
    deposit: Math.round(card.deposit_median_10k_krw),
    monthly: Math.round(card.monthly_median_10k_krw),
    construction_year: null, rate_pct,
  }
  if (card.commute && school) {
    values.school = school
    values.dong = card.commute.campus_area ? null : card.dong
  }
  return values
}
