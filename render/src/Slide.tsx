import { SlideData } from './LearnFlowVideo'

export function Slide({ slide }: { slide: SlideData }) {
  return (
    <div
      style={{
        background: '#1a1a2e',
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        padding: '80px',
        boxSizing: 'border-box',
      }}
    >
      <h1
        style={{
          color: '#e0e0ff',
          fontFamily: 'sans-serif',
          fontSize: '64px',
          margin: '0 0 48px 0',
        }}
      >
        {slide.title}
      </h1>
      <ul
        style={{
          color: '#c0c0e0',
          fontFamily: 'sans-serif',
          fontSize: '40px',
          lineHeight: '1.6',
          paddingLeft: '48px',
          margin: 0,
        }}
      >
        {slide.bullets.map((b, i) => (
          <li key={i}>{b}</li>
        ))}
      </ul>
    </div>
  )
}
