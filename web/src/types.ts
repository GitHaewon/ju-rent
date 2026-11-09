export type ContractInput = {
  campus: string
  housing_type: string
  area: number
  deposit: number
  monthly: number
  construction_year: number | null
  rate_pct: number
}

export type Meta = {
  campuses: string[]
  housing_types: { code: string; name: string; description: string }[]
  rate: {
    default_pct: number
    base_rate_pct: number
    base_rate_date: string
    legal_spread_pct: number
    legal_cap_pct: number
    min_pct: number
    max_pct: number
  }
  data_as_of: string
}

export type Judgment = {
  input: { campus: string; housing_type: string; area_sqm: number; deposit_10k_krw: number; monthly_10k_krw: number; construction_year: number | null }
  rate_pct: number
  converted_monthly_10k_krw: number
  n: number
  step: string
  comparison_period: { start: string; end: string }
  quantiles_10k_krw: { p25: number; p50: number; p75: number; p90: number } | null
  histogram_10k_krw: { left: number; right: number; count: number }[]
  percentile: number | null
  label: string
  age_band_result: { band: string; n: number; percentile: number | null; label: string } | null
  warnings: string[]
  data_as_of: string
}

export type Explanation = { text: string; source: 'ai' | 'rule'; reason: string | null }
