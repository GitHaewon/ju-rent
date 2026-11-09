import { animate, motion, useMotionValue, useMotionValueEvent, useReducedMotion } from 'motion/react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { comparisonSentence, displayWarning, monthPeriod, percentileSentence, rateHint, verdictText } from './copy'
import { axisTicks, pinPlacement, shouldDrawDistribution } from './distribution'
import type { ContractInput, Explanation, Judgment, Meta } from './types'

type FormState = {
  campus: string
  housing_type: string
  area: number
  deposit: string
  monthly: string
  fee: string
  useYear: boolean
  construction_year: string
  rate_pct: number
}

const initialForm: FormState = {
  campus: '', housing_type: '', area: 25, deposit: '500', monthly: '35', fee: '5',
  useYear: false, construction_year: '', rate_pct: 5,
}

const colors: Record<string, string> = {
  '저렴한 편': 'var(--cheap)', '보통': 'var(--normal)',
  '비싼 편': 'var(--pricey)', '많이 비싼 편': 'var(--very)',
  '표본 부족': 'var(--ink-faint)',
}

function format(value: number, digits = 0): string {
  return value.toLocaleString('ko-KR', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

function Count({ value, digits = 0 }: { value: number; digits?: number }) {
  const reduced = useReducedMotion()
  const progress = useMotionValue(value)
  const [display, setDisplay] = useState(value)
  useMotionValueEvent(progress, 'change', setDisplay)
  useEffect(() => {
    if (reduced) {
      progress.set(value)
      setDisplay(value)
      return
    }
    const control = animate(progress, value, { duration: 0.45, ease: [0.2, 0.8, 0.2, 1] })
    return () => control.stop()
  }, [value, progress, reduced])
  return <span>{format(display, digits)}</span>
}

function validate(form: FormState, meta: Meta | null): Record<string, string> {
  if (!meta) return {}
  const errors: Record<string, string> = {}
  if (!Number.isInteger(Number(form.deposit)) || form.deposit.trim() === '' || Number(form.deposit) < 0) {
    errors.deposit = '보증금을 0 이상의 정수로 입력해 주세요.'
  }
  if (!Number.isInteger(Number(form.monthly)) || form.monthly.trim() === '' || Number(form.monthly) <= 0) {
    errors.monthly = '월세를 0보다 큰 정수로 입력해 주세요.'
  }
  if (form.fee.trim() !== '' && (!Number.isInteger(Number(form.fee)) || Number(form.fee) < 0)) {
    errors.fee = '관리비를 0 이상의 정수로 입력해 주세요.'
  }
  if (form.useYear && (!Number.isInteger(Number(form.construction_year)) ||
    Number(form.construction_year) < 1800 || Number(form.construction_year) > Number(meta.data_as_of.slice(0, 4)))) {
    errors.construction_year = '건축년도를 네 자리 숫자로 입력해 주세요.'
  }
  return errors
}

function payload(form: FormState): ContractInput {
  return {
    campus: form.campus,
    housing_type: form.housing_type,
    area: form.area,
    deposit: Number(form.deposit),
    monthly: Number(form.monthly),
    construction_year: form.useYear ? Number(form.construction_year) : null,
    rate_pct: form.rate_pct,
  }
}

function apiErrorField(message: string): string {
  if (message.includes('면적')) return 'area'
  if (message.includes('환산율')) return 'rate_pct'
  if (message.includes('건축년도')) return 'construction_year'
  if (message.includes('보증금') || message.includes('월세')) return 'monthly'
  return 'general'
}

function Distribution({ result }: { result: Judgment }) {
  const bins = result.histogram_10k_krw
  const q = result.quantiles_10k_krw
  const reduced = useReducedMotion()
  const low = bins[0]?.left ?? 0
  const high = bins.at(-1)?.right ?? low + 1
  const draw = shouldDrawDistribution(result.label, bins.length)
  const ticks = axisTicks(low, high)
  const axisLow = ticks[0]
  const axisHigh = ticks.at(-1)!
  const position = (value: number) => Math.min(100, Math.max(0, (value - axisLow) / (axisHigh - axisLow) * 100))
  const pin = pinPlacement(result.converted_monthly_10k_krw, low, high, axisLow, axisHigh)
  const maxCount = Math.max(1, ...bins.map(bin => bin.count))
  const regions = q ? [
    { width: position(q.p25), color: 'var(--cheap)', label: '저렴' },
    { width: position(q.p75) - position(q.p25), color: 'var(--normal)', label: '보통' },
    { width: position(q.p90) - position(q.p75), color: 'var(--pricey)', label: '비싼 편' },
    { width: 100 - position(q.p90), color: 'var(--very)', label: '많이 비쌈' },
  ] : []
  const centers = q ? [
    position((low + q.p25) / 2), position((q.p25 + q.p75) / 2),
    position((q.p75 + q.p90) / 2), position((q.p90 + high) / 2),
  ] : []

  return <section className="dist glass reveal d3" aria-label="비슷한 거래 분포">
    <h3>비슷한 거래 속 이 방의 위치</h3>
    <p className="sub">{draw ? comparisonSentence(result) : `비슷한 거래 ${format(result.n)}건을 찾았어요.`}</p>
    {draw ? <>
      <div className="chart" role="img" aria-label={`환산 월세 분포, 이 방 ${format(result.converted_monthly_10k_krw, 2)}만 원`}>
        <div className="bars">
          {bins.map((bin, index) => <motion.i key={index}
            className={bin.left < result.converted_monthly_10k_krw ? 'on' : ''}
            style={{ left: `${position(bin.left)}%`, width: `max(2px, calc(${position(bin.right) - position(bin.left)}% - 2px))` }}
            initial={false}
            animate={{ height: `${bin.count / maxCount * 100}%` }}
            transition={{ duration: reduced ? 0 : 0.45, ease: [0.2, 0.8, 0.2, 1] }} />)}
        </div>
        {q && <><div className="track">{regions.map((zone, index) =>
          <span key={index} style={{ width: `${zone.width}%`, background: zone.color, opacity: 0.85 }} />)}</div>
          <div className="zones">{regions.map((zone, index) =>
            <em key={zone.label} style={{ left: `${centers[index]}%` }}>{zone.label}</em>)}</div></>}
        <motion.div className={`pin ${pin.edge ? `pin-${pin.edge}` : ''}`} initial={false}
          animate={{ left: `${pin.position}%` }}
          transition={reduced ? { duration: 0 } : { type: 'spring', stiffness: 260, damping: 26 }}>
          <div className="stem" /><div className="dot" /><div className="tag">{pin.tag}</div>
        </motion.div>
      </div>
      <div className="axis">{ticks.map(tick => <span key={tick} style={{ left: `${position(tick)}%` }}>{format(tick)}만 원</span>)}</div>
    </> : <p className="dist-empty">비슷한 거래가 적어 분포를 그리지 않았어요</p>}
  </section>
}

export default function App() {
  const reducedMotion = useReducedMotion()
  const [meta, setMeta] = useState<Meta | null>(null)
  const [form, setForm] = useState<FormState>(initialForm)
  const [result, setResult] = useState<Judgment | null>(null)
  const [settledFee, setSettledFee] = useState(0)
  const [loading, setLoading] = useState(false)
  const [serverError, setServerError] = useState<{ field: string; message: string } | null>(null)
  const [explanation, setExplanation] = useState<Explanation | null>(null)
  const [explainLoading, setExplainLoading] = useState(false)
  const [heroVisible, setHeroVisible] = useState(true)
  const explainAbort = useRef<AbortController | null>(null)
  const heroRef = useRef<HTMLElement | null>(null)
  const errors = useMemo(() => validate(form, meta), [form, meta])

  useEffect(() => {
    const controller = new AbortController()
    fetch('/api/meta', { signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error('설정을 불러오지 못했어요. 잠시 뒤 다시 시도해 주세요.')
        return response.json() as Promise<Meta>
      })
      .then(data => {
        setMeta(data)
        setForm(current => ({ ...current, campus: data.campuses[0],
          housing_type: data.housing_types[0].code, rate_pct: data.rate.default_pct }))
      })
      .catch(error => { if (error.name !== 'AbortError') setServerError({ field: 'general', message: error.message }) })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    if (!meta || !form.campus || !form.housing_type || Object.keys(errors).length) return
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setLoading(true)
      fetch('/api/judge', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload(form)), signal: controller.signal,
      }).then(async response => {
        const data = await response.json()
        if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '입력을 확인해 주세요.')
        return data as Judgment
      }).then(data => { setResult(data); setSettledFee(Number(form.fee || 0)); setServerError(null) })
        .catch(error => { if (error.name !== 'AbortError') setServerError({ field: apiErrorField(error.message), message: error.message }) })
        .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    }, 250)
    return () => { window.clearTimeout(timer); controller.abort() }
  }, [form, meta, errors])

  useEffect(() => {
    const element = heroRef.current
    if (!element) return
    const observer = new IntersectionObserver(([entry]) => setHeroVisible(entry.isIntersecting))
    observer.observe(element)
    return () => observer.disconnect()
  }, [result])

  const update = (change: Partial<FormState>) => {
    explainAbort.current?.abort()
    setExplainLoading(false)
    setExplanation(null)
    setServerError(null)
    setForm(current => ({ ...current, ...change }))
  }

  const explain = async () => {
    if (!result || !resultMatchesForm || Object.keys(errors).length) return
    const controller = new AbortController()
    explainAbort.current = controller
    setExplainLoading(true)
    try {
      const response = await fetch('/api/explain', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload(form)), signal: controller.signal,
      })
      if (!response.ok) throw new Error('설명을 불러오지 못했어요.')
      setExplanation(await response.json() as Explanation)
    } catch (error) {
      if (!(error instanceof DOMException && error.name === 'AbortError')) {
        setExplanation({ text: '기본 판단 결과를 참고해 주세요.', source: 'rule', reason: '연결 오류' })
      }
    } finally { if (!controller.signal.aborted) setExplainLoading(false) }
  }

  const selectedName = meta?.housing_types.find(item => item.code === result?.input.housing_type)?.name ?? ''
  const converted = result?.converted_monthly_10k_krw ?? 0
  const label = result ? verdictText(result) : ''
  const progress = result?.percentile ?? null
  const pillVisible = !!result && !heroVisible
  const resultMatchesForm = !!result && result.input.campus === form.campus &&
    result.input.housing_type === form.housing_type && result.input.area_sqm === form.area &&
    result.input.deposit_10k_krw === Number(form.deposit) &&
    result.input.monthly_10k_krw === Number(form.monthly) &&
    result.input.construction_year === (form.useYear ? Number(form.construction_year) : null) &&
    result.rate_pct === form.rate_pct

  return <div className="shell">
    <header className="brand reveal"><b>JU RENT</b><span>전주 대학가 월세, 계약 전에 확인하세요</span><em className="note">국토교통부 실거래 자료</em></header>
    <div className={`mini glass ${pillVisible ? 'show' : ''}`} aria-hidden={!pillVisible}>
      <b style={{ color: result ? colors[result.label] : undefined }}>{label}</b>
      <span><Count value={converted} digits={2} />만 원</span><a href="#result">결과 보기</a>
    </div>

    <aside className="panel glass reveal d2" aria-label="방 조건">
      <h2>보고 있는 방</h2>
      {loading && <div className="panel-progress" role="progressbar" aria-label="판단 결과 갱신 중" />}
      {serverError?.field === 'general' && <p className="field-error" role="alert">{serverError.message}</p>}
      <div className="field">
        <div className="lab">대학가</div>
        <div className="seg" role="group" aria-label="대학가">
          <motion.span className="thumb" style={{ width: 'calc((100% - 6px) / 2)' }}
            animate={{ x: form.campus === meta?.campuses[1] ? '100%' : '0%' }}
            transition={reducedMotion ? { duration: 0 } : { type: 'spring', stiffness: 260, damping: 26 }} />
          {meta?.campuses.map(campus => <button key={campus} type="button"
            aria-pressed={form.campus === campus} onClick={() => update({ campus })}>{campus}</button>)}
        </div>
        <div className="hint">효자동권은 전주대·전주비전대, 전북대권은 전북대 주변 법정동이에요.</div>
      </div>
      <div className="field">
        <div className="lab">집 종류</div>
        <div className="chips" role="group" aria-label="집 종류">
          {meta?.housing_types.map(kind => <button key={kind.code} type="button"
            aria-pressed={form.housing_type === kind.code} title={kind.description}
            onClick={() => update({ housing_type: kind.code })}>{kind.name}</button>)}
        </div>
      </div>
      <div className="field">
        <label className="range-head" htmlFor="area"><span>전용·계약 면적</span><b>{form.area.toFixed(1)}㎡ · 약 {(form.area / 3.305785).toFixed(1)}평</b></label>
        <input id="area" type="range" min="15" max="45" step="0.5" value={form.area}
          onChange={event => update({ area: Number(event.target.value) })} />
        {serverError?.field === 'area' && <p className="field-error" role="alert">{serverError.message}</p>}
      </div>
      <div className="field row2">
        <div><label htmlFor="dep">보증금</label><div className="num"><input id="dep" type="number" inputMode="numeric"
          min="0" step="1" value={form.deposit} onChange={event => update({ deposit: event.target.value })} /><small>만 원</small></div>
          {errors.deposit && <p className="field-error" role="alert">{errors.deposit}</p>}</div>
        <div><label htmlFor="mon">월세</label><div className="num"><input id="mon" type="number" inputMode="numeric"
          min="1" step="1" value={form.monthly} onChange={event => update({ monthly: event.target.value })} /><small>만 원</small></div>
          {(errors.monthly || serverError?.field === 'monthly') && <p className="field-error" role="alert">{errors.monthly || serverError?.message}</p>}</div>
      </div>
      <div className="field"><label htmlFor="fee">관리비 (선택)</label>
        <div className="num"><input id="fee" type="number" inputMode="numeric" min="0" step="1"
          value={form.fee} onChange={event => update({ fee: event.target.value })} /><small>만 원</small></div>
        {errors.fee && <p className="field-error" role="alert">{errors.fee}</p>}
        <div className="hint">실거래 자료에 관리비가 없어 판단에는 넣지 않고, 매달 내는 돈에만 더해요.</div>
      </div>
      <div className="field"><label className="year-toggle" htmlFor="year-enabled"><span>건축년도 입력 (선택)</span>
        <span className="switch"><input id="year-enabled" type="checkbox" checked={form.useYear}
          onChange={event => update({ useYear: event.target.checked, construction_year: event.target.checked ? String(Number(meta?.data_as_of.slice(0, 4)) - 5) : '' })} />
          <span className="switch-track" aria-hidden="true"><span className="switch-knob" /></span>
        </span></label>
        {form.useYear && <><div className="num"><input id="year" aria-label="건축년도" type="number" inputMode="numeric"
          value={form.construction_year} onChange={event => update({ construction_year: event.target.value })} /></div>
          {(errors.construction_year || serverError?.field === 'construction_year') &&
            <p className="field-error" role="alert">{errors.construction_year || serverError?.message}</p>}</>}
      </div>
      <div className="field"><label className="range-head" htmlFor="rate"><span>보증금 월 환산율</span><b>{form.rate_pct.toFixed(1)}%</b></label>
        <input id="rate" type="range" min={meta?.rate.min_pct ?? 2} max={meta?.rate.max_pct ?? 10}
          step="0.1" value={form.rate_pct} onChange={event => update({ rate_pct: Number(event.target.value) })} />
        {serverError?.field === 'rate_pct' && <p className="field-error" role="alert">{serverError.message}</p>}
        {meta && <div className="hint">{rateHint(meta.rate)}</div>}
      </div>
    </aside>

    <main className="main">
      {result ? <>
        <section className="hero glass reveal d2" id="result" aria-live="polite" ref={heroRef}>
          <div><div className="context">{result.input.campus} {selectedName}, {format(result.input.area_sqm, 1)}㎡</div>
            <div className="verdict" style={{ color: colors[result.label] }}>{label}</div>
            <div className="verdict-line">{progress === null ? percentileSentence(result) :
              <>비슷한 방 100곳 중 <b><Count value={Math.round(progress)} /></b>곳이 이 방보다 쌌어요.</>}</div>
          </div>
          <div className="converted"><div className="big"><Count value={converted} digits={2} /><small>만 원</small></div>
            <p>보증금을 월세로 바꿔 더한 금액이에요</p>
            <p>매달 내는 돈 <b>{format(result.input.monthly_10k_krw + settledFee)}</b>만 원 (월세 + 관리비)</p>
          </div>
        </section>
        <Distribution result={result} />
        <section className="facts">
          {result.quantiles_10k_krw && <div className="fact glass reveal d3"><div className="k">중간값</div>
            <div className="v"><Count value={result.quantiles_10k_krw.p50} digits={2} /><small>만 원</small></div>
            <div className="d">비슷한 거래의 한가운데 가격</div></div>}
          <div className="fact glass reveal d3"><div className="k">비교한 거래</div>
            <div className="v"><Count value={result.n} /><small>건</small></div>
            <div className="d">{monthPeriod(result.comparison_period.start, result.comparison_period.end)}</div></div>
          {result.quantiles_10k_krw && <div className="fact glass reveal d3"><div className="k">비싼 편이 되는 선</div>
            <div className="v"><Count value={result.quantiles_10k_krw.p75} digits={2} /><small>만 원</small></div>
            <div className="d">이보다 비싼 거래는 4곳 중 1곳</div></div>}
        </section>
        {result.age_band_result && <section className="age-card glass" aria-label="건축연도 비교">
          <h3>비슷한 연식의 방과 비교하면</h3>
          <p>{result.age_band_result.band} 거래 {format(result.age_band_result.n)}건 · {result.age_band_result.label}
            {result.age_band_result.percentile !== null && ` · 백분위 ${format(result.age_band_result.percentile, 2)}`}</p>
        </section>}
        <section className="split">
          <div className="card glass reveal d4"><h3>쉽게 풀어보면</h3>
            <p className="ai-text">{explanation ? explanation.text :
              <span className="muted">버튼을 누르면 이 결과를 쉬운 말로 설명해 드려요.</span>}</p>
            {explanation?.source === 'rule' && <p className="hint">AI 설명을 쓰지 못해 기본 설명을 보여드려요({explanation.reason}).</p>}
            <button className="ai-btn" type="button" onClick={explain} disabled={explainLoading || !resultMatchesForm}>
              {explainLoading ? '설명 준비 중…' : 'AI 설명 듣기'}</button>
          </div>
          <div className="card glass reveal d4"><h3>알아두세요</h3>
            <ul className="notes">{result.warnings.map(warning => <li key={warning}>{displayWarning(warning)}</li>)}</ul>
            <div className="source">자료: 국토교통부 실거래가 공개시스템 · 기준일 <span className="source-date">{result.data_as_of}</span></div>
          </div>
        </section>
      </> : <section className="hero glass reveal d2" id="result" aria-live="polite">
        <div className="context">{serverError?.message ?? '실거래 자료를 불러오고 있어요…'}</div>
      </section>}
    </main>
  </div>
}
