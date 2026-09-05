import { spring, useCurrentFrame, useVideoConfig } from 'remotion'
import { DiagramVisual, DiagramNode } from '../LearnFlowVideo'

const CANVAS_SIZE = 1200

function nodePos(n: { x: number; y: number }) {
  return { px: (n.x / 100) * CANVAS_SIZE, py: (n.y / 100) * CANVAS_SIZE }
}

export function Diagram({ visual }: { visual: DiagramVisual }) {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const nodeById: Record<string, DiagramNode> = Object.fromEntries(visual.nodes.map((n) => [n.id, n]))

  return (
    <svg width={CANVAS_SIZE} height={CANVAS_SIZE} viewBox={`0 0 ${CANVAS_SIZE} ${CANVAS_SIZE}`}>
      {visual.edges.map((edge, i) => {
        const from = nodeById[edge.from]
        const to = nodeById[edge.to]
        const a = nodePos(from)
        const b = nodePos(to)
        const drawProgress = spring({ frame: frame - 20 - i * 8, fps, config: { damping: 200 } })
        const midX = a.px + (b.px - a.px) * drawProgress
        const midY = a.py + (b.py - a.py) * drawProgress
        return (
          <g key={i}>
            <line x1={a.px} y1={a.py} x2={midX} y2={midY} stroke="#7c3aed" strokeWidth={4} />
            {edge.label && drawProgress > 0.9 && (
              <text x={(a.px + b.px) / 2} y={(a.py + b.py) / 2 - 12} fill="#c0c0e0" fontSize={22} textAnchor="middle">
                {edge.label}
              </text>
            )}
          </g>
        )
      })}
      {visual.nodes.map((node, i) => {
        const { px, py } = nodePos(node)
        const scale = spring({ frame: frame - i * 6, fps, config: { damping: 12, mass: 0.5 } })
        if (node.shape === 'point') {
          return (
            <g key={node.id} transform={`translate(${px}, ${py}) scale(${scale})`}>
              <circle r={8} fill="#22c55e" />
              <text x={16} y={6} fill="#c0c0e0" fontSize={22}>{node.label}</text>
            </g>
          )
        }
        const shapeEl =
          node.shape === 'circle' ? (
            <circle r={70} fill="#16213e" stroke="#7c3aed" strokeWidth={4} />
          ) : (
            <rect x={-90} y={-50} width={180} height={100} rx={12} fill="#16213e" stroke="#7c3aed" strokeWidth={4} />
          )
        return (
          <g key={node.id} transform={`translate(${px}, ${py}) scale(${scale})`}>
            {shapeEl}
            <text fill="#e0e0ff" fontSize={26} textAnchor="middle" dominantBaseline="middle">
              {node.label}
            </text>
          </g>
        )
      })}
    </svg>
  )
}
