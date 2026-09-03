import { Composition, CalculateMetadataFunction } from 'remotion'
import { LearnFlowVideo, VideoProps, FPS, MIN_SLIDE_SECONDS, slideDurationInFrames } from './LearnFlowVideo'

const calculateMetadata: CalculateMetadataFunction<VideoProps> = ({ props }) => ({
  durationInFrames:
    props.slides.reduce((sum, s) => sum + slideDurationInFrames(s), 0) ||
    Math.ceil(MIN_SLIDE_SECONDS * FPS),
})

const defaultProps: VideoProps = {
  title: 'Untitled',
  slides: [
    {
      index: 0,
      title: 'Slide',
      narration: '',
      bullets: [''],
      audio_static_path: '',
      duration_seconds: MIN_SLIDE_SECONDS,
    },
  ],
}

export function Root() {
  return (
    <Composition
      id="LearnFlowVideo"
      component={LearnFlowVideo}
      calculateMetadata={calculateMetadata}
      durationInFrames={Math.ceil(MIN_SLIDE_SECONDS * FPS)}
      fps={FPS}
      width={1920}
      height={1080}
      defaultProps={defaultProps}
    />
  )
}
