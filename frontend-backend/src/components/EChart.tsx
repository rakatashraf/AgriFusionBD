import { useEffect, useMemo, useRef } from 'react'
import * as echarts from 'echarts/core'
import { LineChart, BarChart, PieChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  LineChart,
  BarChart,
  PieChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  CanvasRenderer,
])

type EChartsOption = Record<string, unknown>

interface Props {
  option: EChartsOption
  height?: number | string
  className?: string
  ariaLabel?: string
}

// Minimal ECharts wrapper (report §4 specifies ECharts, not Recharts).
// Re-renders the chart when the option shape changes; keeps the canvas sized
// to its container via ResizeObserver.
export default function EChart({ option, height = 280, className, ariaLabel }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const chartRef = useRef<echarts.ECharts | null>(null)

  const stableOption = useMemo(() => option, [JSON.stringify(option)])

  useEffect(() => {
    if (!ref.current) return
    const chart = echarts.init(ref.current, undefined, { renderer: 'canvas' })
    chartRef.current = chart
    const ro = new ResizeObserver(() => chart.resize())
    ro.observe(ref.current)
    return () => {
      ro.disconnect()
      chart.dispose()
      chartRef.current = null
    }
  }, [])

  useEffect(() => {
    chartRef.current?.setOption(stableOption, { notMerge: true })
  }, [stableOption])

  return (
    <div
      ref={ref}
      className={className}
      style={{ height }}
      role="img"
      aria-label={ariaLabel ?? 'Chart'}
    />
  )
}
