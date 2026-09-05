import { Audio, Sequence, staticFile } from 'remotion'
import { Slide } from './Slide'

export type CurvePoint = { x: number; y: number }
export type CurveSeries = { label: string; points: CurvePoint[] }
export type CurvePlotVisual = {
  x_label: string
  y_label: string
  x_min: number
  x_max: number
  series: CurveSeries[]
}

export type Bar = { label: string; value: number }
export type BarChartVisual = { y_label: string; bars: Bar[] }

export type DiagramNode = { id: string; label: string; x: number; y: number; shape: 'circle' | 'rect' | 'point' }
export type DiagramEdge = { from: string; to: string; label?: string }
export type DiagramVisual = { nodes: DiagramNode[]; edges: DiagramEdge[] }

export type FormulaAnnotation = { id: string; label: string }
export type FormulaVisual = { latex: string; annotations: FormulaAnnotation[] }

type SlideBase = {
  index: number
  title: string
  narration: string
  bullets: string[]
  audio_static_path: string
  duration_seconds: number
}

export type BulletsSlideData = SlideBase & { type: 'bullets' }
export type CurvePlotSlideData = SlideBase & { type: 'curve_plot'; visual: CurvePlotVisual }
export type BarChartSlideData = SlideBase & { type: 'bar_chart'; visual: BarChartVisual }
export type DiagramSlideData = SlideBase & { type: 'diagram'; visual: DiagramVisual }
export type FormulaSlideData = SlideBase & { type: 'formula'; visual: FormulaVisual }

export type SlideData =
  | BulletsSlideData
  | CurvePlotSlideData
  | BarChartSlideData
  | DiagramSlideData
  | FormulaSlideData

export type VideoProps = {
  title: string
  slides: SlideData[]
}

export const FPS = 30
export const MIN_SLIDE_SECONDS = 3.0

export function slideDurationInFrames(slide: SlideData): number {
  const seconds = Math.max(slide.duration_seconds, MIN_SLIDE_SECONDS)
  return Math.ceil(seconds * FPS)
}

export function LearnFlowVideo({ slides }: VideoProps) {
  let cursor = 0
  return (
    <>
      {slides.map((slide, i) => {
        const durationInFrames = slideDurationInFrames(slide)
        const from = cursor
        cursor += durationInFrames
        return (
          <Sequence key={i} from={from} durationInFrames={durationInFrames}>
            <Slide slide={slide} />
            <Audio src={staticFile(slide.audio_static_path)} />
          </Sequence>
        )
      })}
    </>
  )
}
