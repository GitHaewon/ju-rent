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

export function cardToContract(card: BudgetRecommendation, campus: string, rate_pct: number): ContractInput {
  return {
    campus, housing_type: card.housing_type, area: card.area_median_sqm,
    deposit: Math.round(card.deposit_median_10k_krw),
    monthly: Math.round(card.monthly_median_10k_krw),
    construction_year: null, rate_pct,
  }
}
