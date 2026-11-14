import type { CommuteAccess, Meta } from './types'

export function visibleCommuteDongs(meta: Meta, school: string, housing: string):
  { row: CommuteAccess; count: number; label: string }[] {
  const counts = meta.commute_deal_counts_by_school[school]?.[housing] ?? {}
  return (meta.commute_by_school[school] ?? [])
    .filter(row => !row.campus_area && (counts[row.dong] ?? 0) > 0)
    .map(row => ({ row, count: counts[row.dong],
      label: `${row.dong}${counts[row.dong] < 30 ? ' (거래 적음)' : ''}` }))
}
