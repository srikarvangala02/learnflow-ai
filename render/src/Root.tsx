import { Composition, CalculateMetadataFunction } from 'remotion'
import { LearnFlowVideo, VideoProps, FRAMES_PER_SLIDE } from './LearnFlowVideo'

const calculateMetadata: CalculateMetadataFunction<VideoProps> = ({ props }) => ({
  durationInFrames: Math.max(props.slides.length, 1) * FRAMES_PER_SLIDE,
})

const defaultProps: VideoProps = {
  title: 'Untitled',
  slides: [{ index: 0, title: 'Slide', narration: '', bullets: [''] }],
}

export function Root() {
  return (
    <Composition
      id="LearnFlowVideo"
      component={LearnFlowVideo}
      calculateMetadata={calculateMetadata}
      durationInFrames={150}
      fps={30}
      width={1920}
      height={1080}
      defaultProps={defaultProps}
    />
  )
}
