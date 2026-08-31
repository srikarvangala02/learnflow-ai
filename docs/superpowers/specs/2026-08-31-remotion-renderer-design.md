# Remotion Renderer Design

**Date:** 2026-08-31
**Scope:** Wire script JSON into Remotion slide compositions; implement `POST /render/{job_id}` that shells out to `npx remotion render` as a background task.

---

## 1. Goal

Take the script JSON produced by `POST /generate` and render it as a single `.mp4` video file where each slide is a 5-second static screen (title + bullets). This is the first end-to-end video output for the pipeline; TTS audio is out of scope for this step.

---

## 2. Files

**Create:**
- `render/src/Slide.tsx` — presentational component for a single slide
- `render/src/LearnFlowVideo.tsx` — composition component; routes frames to slides

**Modify:**
- `render/src/Root.tsx` — register `LearnFlowVideo` with dynamic duration via `calculateMetadata`
- `backend/main.py` — add `POST /render/{job_id}` route + `_run_remotion_render` background task

**Create:**
- `backend/tests/test_render_route.py` — integration tests for the new route

---

## 3. Shared Types

Defined inline in `LearnFlowVideo.tsx` and imported by `Slide.tsx`:

```ts
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
```

---

## 4. Remotion Components

### 4a. `render/src/Slide.tsx`

Pure presentational. Renders one slide: dark background (`#1a1a2e`), slide title (white, 64px), bullet list (light lavender `#c0c0e0`, 40px). No animation.

```tsx
import React from 'react'
import { SlideData } from './LearnFlowVideo'

export function Slide({ slide }: { slide: SlideData }) {
  return (
    <div style={{
      background: '#1a1a2e',
      width: '100%',
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      padding: '80px',
      boxSizing: 'border-box',
    }}>
      <h1 style={{ color: '#e0e0ff', fontFamily: 'sans-serif', fontSize: '64px', margin: '0 0 48px 0' }}>
        {slide.title}
      </h1>
      <ul style={{ color: '#c0c0e0', fontFamily: 'sans-serif', fontSize: '40px', lineHeight: '1.6', paddingLeft: '48px', margin: 0 }}>
        {slide.bullets.map((b, i) => <li key={i}>{b}</li>)}
      </ul>
    </div>
  )
}
```

### 4b. `render/src/LearnFlowVideo.tsx`

Composition component. Uses `useCurrentFrame()` to determine the active slide.

```tsx
import React from 'react'
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

export const FRAMES_PER_SLIDE = 150  // 5 s at 30 fps

export function LearnFlowVideo({ slides }: VideoProps) {
  const frame = useCurrentFrame()
  const slideIndex = Math.min(Math.floor(frame / FRAMES_PER_SLIDE), slides.length - 1)
  const slide = slides[slideIndex]
  return <Slide slide={slide} />
}
```

### 4c. `render/src/Root.tsx` (replace entirely)

Registers `LearnFlowVideo` with `calculateMetadata` so Remotion CLI computes the correct total duration from `inputProps`.

```tsx
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
```

---

## 5. Backend: `POST /render/{job_id}`

### Route signature

```
POST /render/{job_id}
  Path param: job_id — the ID of a completed generate job
  Returns:    {"job_id": str}  (a new render_job_id)
  Errors:
    404 if job_id not in jobs store
    400 if job's status is not "complete"
```

### `_run_remotion_render` background task

1. Sets `jobs[render_job_id]["status"] = "running"`
2. Reads `file_id` from `script["file_id"]`
3. Resolves `props_path = (UPLOADS_DIR / f"{file_id}_script.json").resolve()` (absolute)
4. Resolves `out_path = (Path("render/out") / f"{render_job_id}.mp4").resolve()` (absolute)
5. Creates `out_path.parent` if needed
6. Runs:
   ```python
   subprocess.run(
       ["npx", "remotion", "render", "src/index.ts", "LearnFlowVideo",
        str(out_path), "--props", str(props_path)],
       cwd=str(Path("render").resolve()),
       capture_output=True,
       check=False,
   )
   ```
7. On `returncode == 0`: `jobs[render_job_id] = {"status": "complete", "result": {"video_path": str(out_path)}, "error": None}`
8. On non-zero: `jobs[render_job_id] = {"status": "error", "result": None, "error": result.stderr.decode()}`
9. On exception: `jobs[render_job_id] = {"status": "error", "result": None, "error": str(exc)}`

---

## 6. Backend Tests (`backend/tests/test_render_route.py`)

Tests use `unittest.mock.patch("subprocess.run")` — no real `npx` call. The `monkeypatch` fixture ensures `UPLOADS_DIR` points to `tmp_path` and a fake `{file_id}_script.json` exists there.

Scenarios:
- `POST /render/{job_id}` with a complete generate job → 200, returns `job_id`
- `POST /render/{job_id}` with unknown job_id → 404
- `POST /render/{job_id}` where job status is not "complete" → 400
- Background task: subprocess returns 0 → job status `"complete"` with `video_path`
- Background task: subprocess returns non-zero → job status `"error"`

---

## 7. TypeScript Type Checking

Run `npx tsc --noEmit` from `render/` to verify types across all three files. This is the primary quality gate for the Remotion components (no unit test framework).

---

## 8. Constants

| Constant | Value | Location |
|---|---|---|
| `FRAMES_PER_SLIDE` | `150` | `render/src/LearnFlowVideo.tsx` |
| FPS | `30` | `Root.tsx` `<Composition>` |
| Video dimensions | `1920 × 1080` | `Root.tsx` `<Composition>` |
| Slide background | `#1a1a2e` | `Slide.tsx` |
| Title color | `#e0e0ff` | `Slide.tsx` |
| Bullet color | `#c0c0e0` | `Slide.tsx` |

---

## 9. Out of Scope

- TTS audio — narration field is passed to Remotion but not rendered (used in a later step)
- Slide transitions / animations
- Serving the rendered video over HTTP (file path returned in job result is sufficient for demo)
- Remotion Studio preview endpoint
- Concurrent render limiting beyond what `remotion.config.ts` already sets (`concurrency: 1`)
