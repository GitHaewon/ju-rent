import { animate, useMotionValue, useMotionValueEvent, useReducedMotion } from 'motion/react'
import { useEffect, useState } from 'react'

export default function Count({ value, digits = 0 }: { value: number; digits?: number }) {
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
  return <span>{display.toLocaleString('ko-KR', { minimumFractionDigits: digits, maximumFractionDigits: digits })}</span>
}
