import { interpolate, useCurrentFrame, useVideoConfig, spring } from 'remotion'
import { CurvePlotVisual } from '../LearnFlowVideo'

const COLORS = ['#7c3aed', '#22c55e', '#e0e0ff']
const PLOT_WIDTH = 1400
const PLOT_HEIGHT = 700
const MARGIN = 80
// Approximate upper bound on any series' on-screen path length, used only to
// drive the stroke-dasharray "draw in" reveal. It doesn't need to be exact —
// it only needs to exceed the real length so the dash offset fully hides the
// path at progress 0.
const APPROX_PATH_LENGTH = 4000

function toScreen(x: number, y: number, visual: CurvePlotVisual, yMin: number, yMax: number) {
  const ySpan = yMax - yMin || 1
  const px = MARGIN + ((x - visual.x_min) / (visual.x_max - visual.x_min)) * (PLOT_WIDTH - 2 * MARGIN)
  const py = MARGIN + (1 - (y - yMin) / ySpan) * (PLOT_HEIGHT - 2 * MARGIN)
  return { px, py }
}

export function CurvePlot({ visual }: { visual: CurvePlotVisual }) {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()

  const allY = visual.series.flatMap((s) => s.points.map((p) => p.y))
  const yMin = Math.min(...allY)
  const yMax = Math.max(...allY)

  const axisOpacity = spring({ frame, fps, config: { damping: 200 } })

  return (
    <svg width={PLOT_WIDTH} height={PLOT_HEIGHT} viewBox={`0 0 ${PLOT_WIDTH} ${PLOT_HEIGHT}`}>
      <line
        x1={MARGIN} y1={PLOT_HEIGHT - MARGIN} x2={PLOT_WIDTH - MARGIN} y2={PLOT_HEIGHT - MARGIN}
        stroke="#c0c0e0" strokeWidth={2} opacity={axisOpacity}
      />
      <line
        x1={MARGIN} y1={MARGIN} x2={MARGIN} y2={PLOT_HEIGHT - MARGIN}
        stroke="#c0c0e0" strokeWidth={2} opacity={axisOpacity}
      />
      <text x={PLOT_WIDTH / 2} y={PLOT_HEIGHT - 20} fill="#c0c0e0" fontSize={28} textAnchor="middle" opacity={axisOpacity}>
        {visual.x_label}
      </text>
      <text
        x={24} y={PLOT_HEIGHT / 2} fill="#c0c0e0" fontSize={28} textAnchor="middle" opacity={axisOpacity}
        transform={`rotate(-90, 24, ${PLOT_HEIGHT / 2})`}
      >
        {visual.y_label}
      </text>
      {visual.series.map((series, i) => {
        const pathD = series.points
          .map((p, j) => {
            const { px, py } = toScreen(p.x, p.y, visual, yMin, yMax)
            return `${j === 0 ? 'M' : 'L'} ${px} ${py}`
          })
          .join(' ')
        const drawProgress = interpolate(frame, [15 + i * 10, 60 + i * 10], [0, 1], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        })
        return (
          <path
            key={i}
            d={pathD}
            fill="none"
            stroke={COLORS[i % COLORS.length]}
            strokeWidth={5}
            strokeDasharray={APPROX_PATH_LENGTH}
            strokeDashoffset={APPROX_PATH_LENGTH * (1 - drawProgress)}
          />
        )
      })}
      {visual.series.map((series, i) => (
        <text key={i} x={PLOT_WIDTH - MARGIN - 220} y={MARGIN + 30 + i * 36} fill={COLORS[i % COLORS.length]} fontSize={28}>
          {series.label}
        </text>
      ))}
    </svg>
  )
}
