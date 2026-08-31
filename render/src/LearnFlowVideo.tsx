import { useCurrentFrame } from 'remotion'
import { Slide } from './Slide'

export type SlideData = {
  index: number
  title: string
  narration: string
  bullets: string[]
}

export type VideoProps = {
  title: string
  slides: SlideData[]
}

export const FRAMES_PER_SLIDE = 150 // 5 s at 30 fps

export function LearnFlowVideo({ slides }: VideoProps) {
  const frame = useCurrentFrame()
  const slideIndex = Math.min(Math.floor(frame / FRAMES_PER_SLIDE), slides.length - 1)
  const slide = slides[slideIndex]
  if (!slide) return null
  return <Slide slide={slide} />
}
