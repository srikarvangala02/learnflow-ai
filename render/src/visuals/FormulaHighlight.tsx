import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { continueRender, delayRender, spring, useCurrentFrame, useVideoConfig } from 'remotion'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import { FormulaVisual } from '../LearnFlowVideo'

type Position = { x: number; y: number }

export function FormulaHighlight({ visual }: { visual: FormulaVisual }) {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const wrapperRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [positions, setPositions] = useState<Record<string, Position>>({})
  const [handle] = useState(() =>
    delayRender('FormulaHighlight: waiting for KaTeX fonts to load before measuring annotation positions')
  )
  const continuedRef = useRef(false)

  const html = useMemo(
    () =>
      katex.renderToString(visual.latex, {
        throwOnError: false,
        trust: (context) => context.command === '\\htmlId' || context.command === '\\htmlClass',
      }),
    [visual.latex]
  )

  useLayoutEffect(() => {
    let cancelled = false

    // Measuring before KaTeX's web fonts finish loading produces bogus
    // near-origin positions (the browser hasn't laid out the real glyphs
    // yet), which is invisible in a warm Studio session but reproduces
    // reliably in a cold headless render. Waiting on document.fonts.ready
    // guarantees the subsequent getBoundingClientRect() reads reflect the
    // final, correctly-typeset equation.
    document.fonts.ready.then(() => {
      if (cancelled) return
      const container = containerRef.current
      const wrapper = wrapperRef.current
      // Measure against wrapperBox, not the equation container's own box.
      // The SVG overlay below is absolutely positioned relative to the
      // outer wrapper (its nearest `position: relative` ancestor, since
      // the SVG is a sibling of the equation div, not nested inside it).
      // The equation div is centered and narrower than the wrapper, so
      // using the equation div's own bounding box as the coordinate
      // origin left every position short by that centering gap — a
      // constant leftward shift, not the font/scale-timing bug this
      // effect also guards against.
      if (container && wrapper) {
        const wrapperBox = wrapper.getBoundingClientRect()
        const next: Record<string, Position> = {}
        for (const ann of visual.annotations) {
          const el = container.querySelector(`#${CSS.escape(ann.id)}`)
          if (!el) continue
          const box = el.getBoundingClientRect()
          next[ann.id] = {
            x: box.left + box.width / 2 - wrapperBox.left,
            y: box.top + box.height - wrapperBox.top,
          }
        }
        setPositions(next)
      }
      if (!continuedRef.current) {
        continuedRef.current = true
        continueRender(handle)
      }
    })

    return () => {
      cancelled = true
    }
  }, [html, visual.annotations, handle])

  // Opacity, not transform: scale() — a scale transform changes the
  // geometry getBoundingClientRect() reports for this element's children,
  // so measuring while the entrance animation is still under way (e.g. at
  // scale ~0 on the first mounted frame) collapses every htmlId span's
  // bounding box toward the same degenerate point. Opacity never affects
  // layout/bounding-box geometry, so the equation's true position is
  // stable and measurable from frame 0 regardless of the reveal's progress.
  const equationOpacity = spring({ frame, fps, config: { damping: 14, mass: 0.6 } })

  return (
    <div
      ref={wrapperRef}
      style={{
        width: '100%', height: '100%', position: 'relative',
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      }}
    >
      <div
        ref={containerRef}
        style={{ fontSize: 56, color: '#e0e0ff', opacity: equationOpacity, position: 'relative' }}
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
