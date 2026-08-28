import { Composition } from 'remotion'

function LearnFlowSlide() {
  return (
    <div
      style={{
        background: '#1a1a2e',
        width: '100%',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <h1 style={{ color: '#ffffff', fontFamily: 'sans-serif' }}>
        Slide Title
      </h1>
    </div>
  )
}

export function Root() {
  return (
    <Composition
      id="LearnFlowSlide"
      component={LearnFlowSlide}
      durationInFrames={150}
      fps={30}
      width={1920}
      height={1080}
    />
  )
}
