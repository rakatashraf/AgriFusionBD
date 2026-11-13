import { useMemo } from 'react'
import EChart from '#/components/EChart'
import type { FieldIndicator } from '#/lib/types'

interface Props {
  indicators: FieldIndicator[]
  metric: string
  height?: number
}

const METRIC_META: Record<string, { label: string; color: string; unit?: string }> = {
  rainfall_mm: { label: 'Rainfall', color: '#328f97', unit: 'mm' },
  temp_max_c: { label: 'Max temperature', color: '#c9613a', unit: '°C' },
  temp_min_c: { label: 'Min temperature', color: '#3a7cc9', unit: '°C' },
  relative_humidity_pct: { label: 'Relative humidity', color: '#7a5ac9', unit: '%' },
  wind_speed_ms: { label: 'Wind speed', color: '#5a9e5a', unit: 'm/s' },
  shortwave_radiation_mj: { label: 'Solar radiation', color: '#c9a24a', unit: 'MJ/m²/day' },
  ndvi: { label: 'NDVI (HLS)', color: '#2f6a4a', unit: 'index' },
}

export default function IndicatorChart({ indicators, metric, height = 260 }: Props) {
  const meta = METRIC_META[metric] ?? { label: metric, color: '#4fb8b2' }

  const option = useMemo(() => {
    const rows = indicators
      .filter((i) => i.metric === metric)
      .sort((a, b) => a.date.localeCompare(b.date))
    const dates = rows.map((r) => r.date.slice(5))
    const values = rows.map((r) => r.value)
    const coverage = rows.map((r) => r.coveragePct)
    const quality = rows.map((r) => (r.quality === 'ok' ? '#2f6a4a' : r.quality === 'partial' ? '#c9a24a' : '#c44747'))

    return {
      grid: { left: 44, right: 40, top: 28, bottom: 56 },
      tooltip: {
        trigger: 'axis',
        formatter: (params: Array<{ dataIndex: number; value: number }>) => {
          if (!params.length) return ''
          const p = params[0]
          const d = dates[p.dataIndex]
          return `${d}<br/>${meta.label}: <b>${values[p.dataIndex]}</b> ${meta.unit ?? ''}<br/>Coverage: ${coverage[p.dataIndex]}%`
        },
      },
      xAxis: { type: 'category', data: dates, boundaryGap: false, axisLabel: { color: '#416166', hideOverlap: true } },
      yAxis: {
        type: 'value',
        name: meta.unit ?? '',
        axisLabel: { color: '#416166' },
        splitLine: { lineStyle: { color: 'rgba(65,97,102,0.15)' } },
      },
      dataZoom: [{ type: 'inside' }, { type: 'slider', height: 18, bottom: 8, borderColor: 'rgba(65,97,102,0.2)' }],
      series: [
        {
          name: meta.label,
          type: 'line',
          smooth: true,
          symbol: 'circle',
          symbolSize: 4,
          data: values,
          lineStyle: { color: meta.color, width: 2 },
          areaStyle: { opacity: 0.12, color: meta.color },
          itemStyle: { color: quality },
        },
      ],
    }
  }, [indicators, metric, meta])

  return <EChart option={option} height={height} ariaLabel={`${meta.label} over time`} />
}
