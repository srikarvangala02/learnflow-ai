import { ReactNode } from 'react'
import { SlideData } from './LearnFlowVideo'
import { CurvePlot } from './visuals/CurvePlot'
import { BarChart } from './visuals/BarChart'
import { Diagram } from './visuals/Diagram'
import { FormulaHighlight } from './visuals/FormulaHighlight'
import { VisualErrorBoundary } from './visuals/VisualErrorBoundary'

function BulletsLayout({ slide }: { slide: SlideData }) {
  return (
    <div
      style={{
        background: '#1a1a2e', width: '100%', height: '100%',
        display: 'flex', flexDirection: 'column', padding: '80px', boxSizing: 'border-box',
      }}
    >
      <h1 style={{ color: '#e0e0ff', fontFamily: 'sans-serif', fontSize: '64px', margin: '0 0 48px 0' }}>
        {slide.title}
      </h1>
      <ul style={{ color: '#c0c0e0', fontFamily: 'sans-serif', fontSize: '40px', lineHeight: '1.6', paddingLeft: '48px', margin: 0 }}>
        {slide.bullets.map((b, i) => (
          <li key={i}>{b}</li>
        ))}
      </ul>
    </div>
  )
}

function visualFor(slide: SlideData): ReactNode {
  switch (slide.type) {
    case 'curve_plot':
      return <CurvePlot visual={slide.visual} />
    case 'bar_chart':
      return <BarChart visual={slide.visual} />
    case 'diagram':
      return <Diagram visual={slide.visual} />
    case 'formula':
      return <FormulaHighlight visual={slide.visual} />
    case 'bullets':
      return null
  }
}

export function Slide({ slide }: { slide: SlideData }) {
  const bulletsFallback = <BulletsLayout slide={slide} />
  const visualEl = visualFor(slide)

  if (!visualEl) {
    return bulletsFallback
  }

  return (
    <div
      style={{
        background: '#1a1a2e', width: '100%', height: '100%',
        display: 'flex', flexDirection: 'column', padding: '60px', boxSizing: 'border-box',
      }}
    >
      <h1 style={{ color: '#e0e0ff', fontFamily: 'sans-serif', fontSize: '48px', margin: '0 0 24px 0' }}>
        {slide.title}
      </h1>
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <VisualErrorBoundary fallback={bulletsFallback}>{visualEl}</VisualErrorBoundary>
      </div>
    </div>
  )
}
