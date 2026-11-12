import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useEffect, useState } from 'react'
import { EMPTY_BUDGET_MESSAGE, availabilityTone, budgetSummary, cardToContract, tenDealSentence, typicalTerms } from './areaCopy'
import Count from './Count'
import { rateHint } from './copy'
import { housingName } from './housing'
import type { BudgetRecommendation, BudgetResult, CampusComparison, ContractInput, Meta, PriceTrend } from './types'

type SharedProps = { meta: Meta; rate: number; onRateChange: (rate: number) => void }
type BudgetProps = SharedProps & { onChoose: (values: ContractInput) => void }
type Priority = 'cheap' | 'new' | 'large'
type BudgetHousing = 'oneroom' | 'officetel' | 'apartment' | null

const priorityOptions: { code: Priority; name: string }[] = [
  { code: 'cheap', name: '저렴하게' }, { code: 'new', name: '새 건물' }, { code: 'large', name: '넓게' },
]
const budgetHousing: { code: BudgetHousing; name: string }[] = [
  { code: null, name: '전체' }, { code: 'oneroom', name: '원룸·투룸·빌라' },
  { code: 'officetel', name: '오피스텔' }, { code: 'apartment', name: '아파트' },
]

function readableError(response: Response, body: { detail?: string }): string {
  return response.ok ? '' : typeof body.detail === 'string' ? body.detail : '자료를 불러오지 못했어요. 잠시 뒤 다시 시도해 주세요.'
}

function SourceNote({ date }: { date: string }) {
  return <p className="area-source">자료: 국토교통부 실거래가 공개시스템 · 기준일 <span className="source-date">{date}</span><br />
    실거래 자료에는 관리비가 없어요. 과거 계약 기준이며 지금 나와 있는 매물 가격이 아니에요.
  </p>
}

function BudgetCard({ card, campus, rate, onChoose }: {
  card: BudgetRecommendation; campus: string; rate: number; onChoose: BudgetProps['onChoose']
}) {
  const reduced = useReducedMotion()
  return <motion.button layout type="button" className="budget-card glass"
    initial={{ opacity: 0, y: reduced ? 0 : 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: reduced ? 0 : -8 }}
    transition={{ duration: reduced ? 0 : 0.25, ease: [0.2, 0.8, 0.2, 1] }}
    onClick={() => onChoose(cardToContract(card, campus, rate))}
    aria-label={`${card.dong} ${housingName(card.housing_type)} ${card.age_band}, 계약 판단에서 보기`}>
    <span className="budget-card-head"><span><strong>{card.dong}</strong><small>{housingName(card.housing_type)} · {card.age_band}</small></span>
      <span className={`availability ${availabilityTone(card.availability_label)}`}>{card.availability_label}</span></span>
    <span className="budget-terms">{typicalTerms(card)}</span>
    <span className="budget-typical-note">{card.typical_terms_note}</span>
    <span className="budget-bar-copy">{tenDealSentence(card)} <em>· 거래 <Count value={card.n} />건</em></span>
    <span className="budget-bar" role="img" aria-label={`예산 안 비율 ${card.within_budget_pct.toFixed(1)}%`}>
      <motion.span initial={false} animate={{ width: `${card.within_budget_pct}%` }}
        transition={{ duration: reduced ? 0 : 0.45, ease: [0.2, 0.8, 0.2, 1] }} /></span>
    <span className="budget-card-action">이 조건으로 계약 판단하기 <span aria-hidden="true">→</span></span>
  </motion.button>
}

export function BudgetView({ meta, rate, onRateChange, onChoose }: BudgetProps) {
  const reduced = useReducedMotion()
  const [campus, setCampus] = useState(meta.campuses[0])
  const [deposit, setDeposit] = useState('500')
  const [monthly, setMonthly] = useState('35')
  const [minArea, setMinArea] = useState(15)
  const [housing, setHousing] = useState<BudgetHousing>(null)
  const [priority, setPriority] = useState<Priority>('cheap')
  const [collapsed, setCollapsed] = useState(false)
  const [showAll, setShowAll] = useState(false)
  const [result, setResult] = useState<BudgetResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const minimum = housing === 'apartment' ? 40 : 15
  const maximum = housing === null || housing === 'apartment' ? 132 : 45
  const valid = deposit.trim() !== '' && monthly.trim() !== '' &&
    Number.isFinite(Number(deposit)) && Number.isFinite(Number(monthly)) &&
    Number(deposit) >= 0 && Number(monthly) >= 0

  useEffect(() => {
    if (!valid) {
      setResult(null)
      setError('보증금과 월세 예산을 0 이상의 숫자로 입력해 주세요.')
      setLoading(false)
      return
    }
    setError(null)
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setLoading(true)
      fetch('/api/budget', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
        body: JSON.stringify({ campus, deposit: Number(deposit), monthly: Number(monthly),
          min_area: minArea, housing, priority, rate_pct: rate }),
      }).then(async response => {
        const body = await response.json()
        if (!response.ok) throw new Error(readableError(response, body))
        return body as BudgetResult
      }).then(data => { setResult(data); setShowAll(false); setError(null) })
        .catch(cause => { if (cause.name !== 'AbortError') setError(cause.message) })
        .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    }, 250)
    return () => { window.clearTimeout(timer); controller.abort() }
  }, [campus, deposit, monthly, minArea, housing, priority, rate, valid])

  const changeHousing = (choice: BudgetHousing) => {
    setHousing(choice)
    const low = choice === 'apartment' ? 40 : 15
    const high = choice === null || choice === 'apartment' ? 132 : 45
    setMinArea(current => Math.min(high, Math.max(low, current)))
  }
  const displayed = result && result.input.campus === campus && result.input.deposit_10k_krw === Number(deposit) &&
    result.input.monthly_10k_krw === Number(monthly) && result.input.min_area_sqm === minArea &&
    result.input.housing_type === housing && result.input.priority === priority && result.rate_pct === rate ? result : null
  const recommendations = displayed?.recommendations ?? []
  return <>
    <aside className="panel glass budget-panel" aria-label="예산 조건">
      <div className="budget-panel-head"><h2>예산으로 찾기</h2>
        <button type="button" className="budget-collapse" aria-expanded={!collapsed} aria-controls="budget-fields"
          onClick={() => setCollapsed(current => !current)}>{collapsed ? '조건 펼치기' : '조건 접기'}</button></div>
      {!collapsed && <div id="budget-fields">
        <div className="field"><div className="lab">대학가</div><div className="seg" role="group" aria-label="예산 대학가">
          <motion.span className="thumb" style={{ width: 'calc((100% - 6px) / 2)' }}
            animate={{ x: campus === meta.campuses[1] ? '100%' : '0%' }}
            transition={reduced ? { duration: 0 } : { type: 'spring', stiffness: 260, damping: 26 }} />
          {meta.campuses.map(name => <button key={name} type="button" aria-pressed={campus === name}
            onClick={() => setCampus(name)}>{name}</button>)}
        </div><div className="hint">캠퍼스 주변 법정동을 기준으로 비교해요.</div></div>
        <div className="field row2"><div><label htmlFor="budget-deposit">가진 보증금</label>
          <div className="num"><input id="budget-deposit" type="number" inputMode="decimal" min="0" step="0.0001"
            value={deposit} onChange={event => setDeposit(event.target.value)} /><small>만 원</small></div></div>
          <div><label htmlFor="budget-monthly">월세 예산</label>
            <div className="num"><input id="budget-monthly" type="number" inputMode="decimal" min="0" step="0.0001"
              value={monthly} onChange={event => setMonthly(event.target.value)} /><small>만 원</small></div></div></div>
        <div className="field"><label className="range-head" htmlFor="budget-area"><span>최소 면적</span>
          <b>{minArea.toFixed(1)}㎡ · 약 {(minArea / 3.305785).toFixed(1)}평</b></label>
          <input id="budget-area" type="range" min={minimum} max={maximum} step="0.5" value={minArea}
            onChange={event => setMinArea(Number(event.target.value))} /></div>
        <div className="field"><div className="lab">집 종류</div><div className="chips" role="group" aria-label="예산 집 종류">
          {budgetHousing.map(choice => <button key={choice.code ?? 'all'} type="button"
            aria-pressed={housing === choice.code} onClick={() => changeHousing(choice.code)}>{choice.name}</button>)}
        </div></div>
        <div className="field"><div className="lab">무엇을 먼저 볼까요?</div>
          <div className="seg" role="group" aria-label="우선순위">
            <motion.span className="thumb" style={{ width: 'calc((100% - 6px) / 3)' }}
              animate={{ x: `${priorityOptions.findIndex(option => option.code === priority) * 100}%` }}
              transition={reduced ? { duration: 0 } : { type: 'spring', stiffness: 260, damping: 26 }} />
            {priorityOptions.map(option => <button key={option.code} type="button"
              aria-pressed={priority === option.code} onClick={() => setPriority(option.code)}>{option.name}</button>)}
          </div></div>
        <div className="field"><label className="range-head" htmlFor="budget-rate"><span>보증금 월 환산율</span>
          <b>{rate.toFixed(1)}%</b></label>
          <input id="budget-rate" type="range" min={meta.rate.min_pct} max={meta.rate.max_pct} step="0.1"
            value={rate} onChange={event => onRateChange(Number(event.target.value))} />
          <div className="hint">{rateHint(meta.rate)}</div></div>
      </div>}
    </aside>
    <main className="main budget-main" aria-busy={loading}>
      {error && <p className="field-error glass area-message" role="alert">{error}</p>}
      {!displayed && !error && <section className="hero glass area-message" role="status">집 조건을 찾고 있어요…</section>}
      {displayed && <>
        <section className="hero glass budget-summary" aria-live="polite"><div>
          <div className="context">{campus} · 최근 24개월 계약</div>
          <h1 aria-label={budgetSummary(recommendations.length)}>조건에 맞는 선택지 <Count value={recommendations.length} />개를 찾았어요</h1>
          <p>예산에 맞았던 과거 거래를 바탕으로 살펴볼 만한 집 조건이에요.</p></div></section>
        {recommendations.length ? <div className="budget-list" aria-label="예산 추천 목록">
          <AnimatePresence mode="popLayout">{(showAll ? recommendations : recommendations.slice(0, 8)).map(card =>
            <BudgetCard key={`${card.dong}-${card.housing_type}-${card.age_band}`} card={card} campus={displayed.input.campus}
              rate={displayed.rate_pct} onChoose={onChoose} />)}</AnimatePresence>
        </div> : <section className="card glass budget-empty"><h2>맞는 집을 찾기 어려워요</h2><p>{EMPTY_BUDGET_MESSAGE}</p></section>}
        {!showAll && recommendations.length > 8 && <button className="ai-btn budget-more" type="button"
          onClick={() => setShowAll(true)}>더 보기</button>}
        <section className="card glass exclusion-note" aria-label="제외한 집 조건"><h3>결과에서 뺀 조건</h3>
          <p>거래가 적어서 <b><Count value={displayed.excluded_counts.sample_shortage} />개</b> · 한 건물에 몰려서 <b><Count value={displayed.excluded_counts.complex_concentration} />개</b> · 예산 밖 <b><Count value={displayed.excluded_counts.under_25_pct} />개</b></p>
          <SourceNote date={displayed.data_as_of} /></section>
      </>}
    </main>
  </>
}

function decimal(value: number): string {
  return value.toLocaleString('ko-KR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
}

function TrendChart({ rows, campuses }: { rows: PriceTrend[]; campuses: string[] }) {
  const values = rows.map(row => row.converted_median_10k_krw).filter((value): value is number => value !== null)
  const low = Math.min(...values) - 2
  const high = Math.max(...values) + 2
  const y = (value: number) => 196 - (value - low) / (high - low) * 150
  const x = (index: number) => 44 + index * 125
  const years = [...new Set(rows.map(row => row.year))].sort()
  return <div className="trend-chart">
    <div className="trend-legend">{campuses.map((campus, index) => <span key={campus}>
      <i style={{ background: index === 0 ? 'var(--normal)' : 'var(--very)' }} />{campus}</span>)}</div>
    <svg viewBox="0 0 720 245" role="img" aria-label="두 대학가의 원룸·투룸·빌라 25~35㎡ 연도별 월세 비교">
      {years.map((year, index) => <text key={year} x={x(index)} y="228" textAnchor="middle" className="trend-year">
        {year === 2026 ? '2026*' : year}</text>)}
      {campuses.map((campus, index) => {
        const points = rows.filter(row => row.campus === campus).sort((a, b) => a.year - b.year)
          .map((row, pointIndex) => ({ row, x: x(pointIndex), y: y(row.converted_median_10k_krw ?? low) }))
        const color = index === 0 ? 'var(--normal)' : 'var(--very)'
        return <g key={campus} fill="none" stroke={color} strokeWidth="3">
          <polyline points={points.slice(0, 5).map(point => `${point.x},${point.y}`).join(' ')} />
          <line x1={points[4].x} y1={points[4].y} x2={points[5].x} y2={points[5].y} strokeDasharray="8 6" />
          {points.map(point => <circle key={point.row.year} cx={point.x} cy={point.y} r="5" fill="white">
            <title>{campus} {point.row.year}년 {point.row.converted_median_10k_krw === null ? '표본 부족' : `${decimal(point.row.converted_median_10k_krw)}만 원`}</title>
          </circle>)}
        </g>
      })}
    </svg>
    <p className="hint">* 2026년은 1~10월 계약이며 점선으로 표시했어요.</p>
    <div className="trend-values">{rows.map(row => <div key={`${row.campus}-${row.year}`}>
      <span>{row.campus} · {row.year}년{row.partial_year ? ' 1~10월' : ''}</span>
      <b>{row.converted_median_10k_krw === null ? '표본 부족' : `${decimal(row.converted_median_10k_krw)}만 원`}</b></div>)}</div>
  </div>
}

export function CompareView({ meta, rate, onRateChange }: SharedProps) {
  const [result, setResult] = useState<CampusComparison | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError(null)
    fetch(`/api/compare?rate_pct=${rate}`, { signal: controller.signal })
      .then(async response => {
        const body = await response.json()
        if (!response.ok) throw new Error(readableError(response, body))
        return body as CampusComparison
      }).then(data => { setResult(data); setError(null) })
      .catch(cause => { if (cause.name !== 'AbortError') setError(cause.message) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [rate])
  const displayed = result?.rate_pct === rate ? result : null
  return <main className="main compare-main" aria-busy={loading}>
    <section className="hero glass compare-intro"><div><div className="context">전주 대학가 월세 비교</div>
      <h1>두 대학가를 나란히 살펴봐요</h1><p>최근 24개월의 새 계약과 미기재 계약을 비교했어요.</p></div>
      <div className="compare-rate"><label className="range-head" htmlFor="compare-rate"><span>보증금 월 환산율</span>
        <b>{rate.toFixed(1)}%</b></label><input id="compare-rate" type="range" min={meta.rate.min_pct}
          max={meta.rate.max_pct} step="0.1" value={rate} onChange={event => onRateChange(Number(event.target.value))} />
        <div className="hint">{rateHint(meta.rate)}</div></div></section>
    {error && <p className="field-error glass area-message" role="alert">{error}</p>}
    {!displayed && !error && <p className="card glass area-message" role="status">비교 자료를 불러오고 있어요…</p>}
    {displayed && <>
      <div className="compare-grid">{meta.campuses.map(campus => <section className="card glass compare-card" key={campus}>
        <h2>{campus}</h2><p className="compare-card-sub">집 종류와 면적에 따라 비교해요.</p>
        <table className="compare-table"><thead><tr><th scope="col">집 종류·면적</th><th scope="col">월세 수준</th>
          <th scope="col">보통 계약 조건</th><th scope="col">거래</th></tr></thead><tbody>
          {displayed.area_bands.filter(row => row.campus === campus).map(row => <tr key={`${row.housing_type}-${row.area_band}`}>
            <th scope="row"><strong>{housingName(row.housing_type)}</strong><small>{row.area_band}</small></th>
            <td data-label="월세 수준">{row.sample_note ? <span className="sample-pill">표본 부족</span> : <>
              <b>{decimal(row.quantiles_10k_krw!.p50)}만 원</b><small>25~75%: {decimal(row.quantiles_10k_krw!.p25)}~{decimal(row.quantiles_10k_krw!.p75)}만 원</small></>}</td>
            <td data-label="보통 계약 조건">{row.sample_note ? '—' : <span>
              보증금 {decimal(row.deposit_median_10k_krw!)}만 원<br />월세 {decimal(row.monthly_median_10k_krw!)}만 원</span>}</td>
            <td data-label="거래">{row.n.toLocaleString('ko-KR')}건</td>
          </tr>)}</tbody></table></section>)}</div>
      <section className="card glass trend-section"><h2>원룸·투룸·빌라 월세 흐름</h2>
        <p>25~35㎡의 연도별 한가운데 가격이에요. 보증금을 월세로 바꿔 더했어요.</p>
        <TrendChart rows={displayed.yearly_trend} campuses={meta.campuses} /></section>
      <SourceNote date={displayed.data_as_of} />
    </>}
  </main>
}
