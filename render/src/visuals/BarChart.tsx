import { spring, useCurrentFrame, useVideoConfig } from 'remotion'
import { BarChartVisual } from '../LearnFlowVideo'

const CHART_WIDTH = 1400
const CHART_HEIGHT = 700
const MARGIN = 80
const BAR_COLOR = '#7c3aed'

export function BarChart({ visual }: { visual: BarChartVisual }) {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()

  const maxValue = Math.max(...visual.bars.map((b) => b.value)) || 1
  const plotHeight = CHART_HEIGHT - 2 * MARGIN
  const plotWidth = CHART_WIDTH - 2 * MARGIN
  const gap = plotWidth / visual.bars.length
  const barWidth = gap / 1.6

  return (
    <svg width={CHART_WIDTH} height={CHART_HEIGHT} viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}>
      <line
        x1={MARGIN} y1={CHART_HEIGHT - MARGIN} x2={CHART_WIDTH - MARGIN} y2={CHART_HEIGHT - MARGIN}
        stroke="#c0c0e0" strokeWidth={2}
      />
      <text x={CHART_WIDTH / 2} y={30} fill="#c0c0e0" fontSize={28} textAnchor="middle">
        {visual.y_label}
      </text>
      {visual.bars.map((bar, i) => {
        const growth = spring({ frame: frame - i * 6, fps, config: { damping: 15, mass: 0.6 } })
        const barHeight = (bar.value / maxValue) * plotHeight * Math.max(growth, 0)
        const x = MARGIN + i * gap + (gap - barWidth) / 2
        const y = CHART_HEIGHT - MARGIN - barHeight
        return (
          <g key={i}>
            <rect x={x} y={y} width={barWidth} height={barHeight} fill={BAR_COLOR} rx={6} />
            <text x={x + barWidth / 2} y={CHART_HEIGHT - MARGIN + 36} fill="#c0c0e0" fontSize={24} textAnchor="middle">
              {bar.label}
            </text>
            <text x={x + barWidth / 2} y={y - 14} fill="#e0e0ff" fontSize={24} textAnchor="middle">
              {bar.value}
            </text>
          </g>
        )
      })}
    </svg>
  )
}
