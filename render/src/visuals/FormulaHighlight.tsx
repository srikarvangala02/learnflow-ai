import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { spring, useCurrentFrame, useVideoConfig } from 'remotion'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import { FormulaVisual } from '../LearnFlowVideo'

type Position = { x: number; y: number }

export function FormulaHighlight({ visual }: { visual: FormulaVisual }) {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const containerRef = useRef<HTMLDivElement>(null)
  const [positions, setPositions] = useState<Record<string, Position>>({})

  const html = useMemo(
    () =>
      katex.renderToString(visual.latex, {
        throwOnError: false,
        trust: (context) => context.command === '\\htmlId' || context.command === '\\htmlClass',
      }),
    [visual.latex]
  )

  useLayoutEffect(() => {
    const container = containerRef.current
    if (!container) return
    const containerBox = container.getBoundingClientRect()
    const next: Record<string, Position> = {}
    for (const ann of visual.annotations) {
      const el = container.querySelector(`#${CSS.escape(ann.id)}`)
      if (!el) continue
      const box = el.getBoundingClientRect()
      next[ann.id] = {
        x: box.left + box.width / 2 - containerBox.left,
        y: box.top + box.height - containerBox.top,
      }
    }
    setPositions(next)
  }, [html, visual.annotations])

  const equationScale = spring({ frame, fps, config: { damping: 14, mass: 0.6 } })

  return (
    <div
      style={{
        width: '100%', height: '100%', position: 'relative',
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      }}
    >
      <div
        ref={containerRef}
        style={{ fontSize: 56, color: '#e0e0ff', transform: `scale(${equationScale})`, position: 'relative' }}
        dangerouslySetInnerHTML={{ __html: html }}
      />
      <svg style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none' }}>
        {visual.annotations.map((ann, i) => {
          const pos = positions[ann.id]
          if (!pos) return null
          const reveal = spring({ frame: frame - 30 - i * 15, fps, config: { damping: 200 } })
          if (reveal <= 0) return null
          const labelY = pos.y + 60 + i * 44
          return (
            <g key={ann.id} opacity={reveal}>
              <line x1={pos.x} y1={pos.y} x2={pos.x} y2={labelY - 10} stroke="#7c3aed" strokeWidth={3} />
              <circle cx={pos.x} cy={pos.y} r={5} fill="#7c3aed" />
              <text x={pos.x} y={labelY + 10} fill="#c0c0e0" fontSize={24} textAnchor="middle">
                {ann.label}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}
