import type { Judgment } from './types'

export function freshnessLabel(end: string, refreshed?: string): string {
  const [year, month] = end.split('-')
  if (!refreshed) return `실거래 기준: ${year}년 ${Number(month)}월 계약까지`
  const [, updatedMonth, updatedDay] = refreshed.split('-')
  return `실거래 기준: ${year}년 ${Number(month)}월 계약까지 · ${Number(updatedMonth)}월 ${Number(updatedDay)}일 갱신`
}

const WARNING_COPY: Record<string, string> = {
  '실거래 자료에는 관리비가 포함되지 않습니다.': '실거래 자료에는 관리비가 없어요.',
  '대학가 법정동 범위는 캠퍼스 도보권의 대리범위입니다.': '대학가는 캠퍼스 주변 법정동 기준이라 실제 도보 거리와 다를 수 있어요.',
  '실거래는 과거 계약이며 현재 공실·호가가 아닙니다.': '과거 계약 기준이며 지금 나와 있는 매물 가격이 아니에요.',
  '2026년 최근 2개월은 신고 미반영으로 불완전할 수 있습니다.': '2026년 9~10월 계약은 아직 신고가 덜 들어왔을 수 있어요.',
}

export function displayWarning(warning: string): string {
  return WARNING_COPY[warning] ?? warning
}

export function verdictText(result: Pick<Judgment, 'label'>): string {
  return result.label === '표본 부족' ? '판단 보류' : result.label
}

export function percentileSentence(result: Pick<Judgment, 'label' | 'percentile' | 'n'> & { reason?: string | null }): string {
  if (result.label === '판단 보류' || result.label === '제공 안 함') {
    return result.reason ?? '이 조건의 비교 판단을 제공하지 않아요.'
  }
  if (result.label === '표본 부족' || result.percentile === null) {
    return `비슷한 거래가 ${result.n.toLocaleString('ko-KR')}건뿐이라 판단하기 어려워요. 면적이나 집 종류를 바꿔 보세요.`
  }
  return `비슷한 방 100곳 중 ${Math.round(result.percentile)}곳이 이 방보다 쌌어요.`
}

export function comparisonSentence(result: Pick<Judgment, 'step' | 'n' | 'comparison_period'>): string {
  const range = result.step === '기간 확대'
    ? '2021년부터로 넓혀'
    : result.step === '면적 ±10㎡'
      ? '최근 24개월, 같은 집 종류, 면적 ±10㎡로 넓혀'
      : '최근 24개월, 같은 집 종류, 면적 ±5㎡'
  return `${range} 거래 ${result.n.toLocaleString('ko-KR')}건의 환산 월세 분포예요.`
}

export function negotiationSentence(hint: Judgment['hint'], label: Judgment['label']): string | null {
  if (!hint) return null
  if (hint.monthly_reduction_10k_krw !== null) {
    return `월세를 ${hint.monthly_reduction_10k_krw}만 원 낮추면 '보통'이 돼요`
  }
  if (label === '비싼 편' || label === '많이 비싼 편') {
    return "월세만 깎아서는 '보통'이 되기 어려워요"
  }
  const difference = hint.difference_from_median_10k_krw
  if (difference === 0) return '중간값과 같아요'
  const direction = difference >= 0 ? '비싸요' : '싸요'
  return `중간값보다 ${Math.abs(difference).toFixed(2)}만 원 ${direction}`
}

export function monthPeriod(start: string, end: string): string {
  const [sy, sm] = start.split('-')
  const [ey, em] = end.split('-')
  return `${sy}년 ${Number(sm)}월 ~ ${ey}년 ${Number(em)}월 계약`
}

export function rateHint(rate: { default_pct: number; base_rate_pct: number; base_rate_date: string; legal_spread_pct: number }): string {
  const [y, m, d] = rate.base_rate_date.split('-')
  return `기본 ${rate.default_pct.toFixed(1)}%는 법정 전환율 상한(기준금리 ${rate.base_rate_pct.toFixed(2)}% + ${rate.legal_spread_pct.toFixed(0)}%p, ${y}년 ${Number(m)}월 ${Number(d)}일 기준)이에요.`
}
