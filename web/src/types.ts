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
  converted_monthly_10k_krw: number | null
  n: number
  step: string | null
  comparison_period: { start: string; end: string } | null
  quantiles_10k_krw: { p25: number; p50: number; p75: number; p90: number } | null
  histogram_10k_krw: { left: number; right: number; count: number }[]
  percentile: number | null
  label: string
  reason: string | null
  complex_concentration: { dong: string; lot: string; name: string; count: number; share_pct: number } | null
  hint: { difference_from_median_10k_krw: number; monthly_reduction_10k_krw: number | null } | null
  age_band_result: { band: string; n: number; percentile: number | null; label: string } | null
  warnings: string[]
  data_as_of: string
}

export type Explanation = { text: string; source: 'ai' | 'rule'; reason: string | null }

export type BudgetRecommendation = {
  dong: string
  housing_type: string
  age_band: string
  n: number
  within_budget_count: number
  within_budget_pct: number
  availability_label: string
  quantiles_10k_krw: { p25: number; p50: number; p75: number }
  deposit_median_10k_krw: number
  monthly_median_10k_krw: number
  area_median_sqm: number
  typical_terms_note: string
}

export type BudgetResult = {
  input: { campus: string; deposit_10k_krw: number; monthly_10k_krw: number; min_area_sqm: number; housing_type: string | null; priority: string }
  rate_pct: number
  data_as_of: string
  total_combinations: number
  total_deals: number
  excluded_counts: { sample_shortage: number; complex_concentration: number; under_25_pct: number }
  recommendations: BudgetRecommendation[]
}

export type AreaBand = {
  campus: string
  housing_type: string
  area_band: string
  period_start: string
  period_end: string
  n: number
  sample_note: string
  quantiles_10k_krw: { p25: number; p50: number; p75: number } | null
  deposit_median_10k_krw: number | null
  monthly_median_10k_krw: number | null
}

export type PriceTrend = {
  campus: string
  housing_type: string
  area_band: string
  year: number
  period_start: string
  period_end: string
  partial_year: boolean
  n: number
  converted_median_10k_krw: number | null
  sample_note: string
}

export type CampusComparison = {
  rate_pct: number
  data_as_of: string
  area_bands: AreaBand[]
  yearly_trend: PriceTrend[]
}
