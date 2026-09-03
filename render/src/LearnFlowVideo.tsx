import { Audio, Sequence, staticFile } from 'remotion'
import { Slide } from './Slide'

export type SlideData = {
  index: number
  title: string
  narration: string
  bullets: string[]
  audio_static_path: string
  duration_seconds: number
}

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
