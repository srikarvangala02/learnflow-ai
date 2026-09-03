# TTS Integration Design

**Date:** 2026-09-03
**Scope:** Wire ElevenLabs text-to-speech into the pipeline so narration is actually spoken in the rendered video, with slide display time driven by real audio length.

---

## 1. Goal

Today, `POST /generate` produces narration as text only. `elevenlabs` sits unused in `requirements.txt`, and `LearnFlowVideo.tsx` renders silent slides for a fixed 5 seconds each (`FRAMES_PER_SLIDE = 150`). This design closes that gap: each slide's narration is synthesized to an MP3 via ElevenLabs, its real duration drives that slide's on-screen time (bounded so pacing stays sane), and the Remotion composition plays the audio in sync with the slide.

---

## 2. Files

**Create:**
- `backend/tts_generator.py` — TTS synthesis module
- `backend/tests/test_tts_generator.py` — unit tests for it

**Modify:**
- `backend/requirements.txt` — add `mutagen` (MP3 duration reading)
- `backend/script_generator.py` — cap spoken narration length in the generation prompt
- `backend/main.py` — call TTS synthesis inside `_run_generate`; build render-time audio props inside `_run_remotion_render`
- `backend/tests/test_routes.py` — cover TTS wiring into `/generate`
- `backend/tests/test_render_route.py` — cover the render-time audio copy step
- `render/src/LearnFlowVideo.tsx` — per-slide `<Sequence>` + `<Audio>`, variable duration
- `render/src/Root.tsx` — `calculateMetadata` sums real per-slide durations

---

## 3. TTS Synthesis (`backend/tts_generator.py`)

One function: `synthesize_slide_audio(file_id, slides, uploads_dir) -> list[dict]`.

For each slide, calls ElevenLabs' `text_to_speech.convert(voice_id=..., text=slide["narration"], model_id="eleven_multilingual_v2", output_format="mp3_44100_128")`, which returns an `Iterator[bytes]`. The joined bytes are written to `uploads/{file_id}/audio/slide_{index}.mp3`. Returns the same slides with two fields merged in: `audio_path` (resolved absolute path, string) and `duration_seconds` (float).

**Missing key handling** mirrors `generate_script`'s existing `ANTHROPIC_API_KEY` check exactly: if `ELEVENLABS_API_KEY` is unset, raise `ValueError` before making any network call. Since this call happens inside `_run_generate`'s existing `try/except Exception` block, the job fails cleanly with `status: "error"` — no new error-handling path needed.

**Voice selection:** `ELEVENLABS_VOICE_ID` env var, falling back to a hardcoded default (`21m00Tcm4TlvDq8ikWAM`, ElevenLabs' standard "Rachel" sample voice) if unset. No voice-selection UI — out of scope per the README's MVP scope.

---

## 4. Duration Extraction

Use `mutagen` (`from mutagen.mp3 import MP3; MP3(path).info.length`) to read the duration directly from the MP3 file that was just written to disk — not a value ElevenLabs' API response might report. This is the ground truth for what Remotion will actually play, and it's a lightweight header read (no full decode), so it doesn't meaningfully slow down the generate job.

---

## 5. Variable Slide Timing — Floor, Ceiling, and What Happens Past 12s

Two constants, defined identically in both `tts_generator.py` (Python, for the warning check) and `LearnFlowVideo.tsx` (TypeScript, for the floor clamp):

```
MIN_SLIDE_SECONDS = 3.0
MAX_SLIDE_SECONDS = 12.0
```

**Floor (hard clamp):** A slide always displays for at least 3 seconds, even if its narration audio is shorter. Remotion computes `displaySeconds = max(duration_seconds, MIN_SLIDE_SECONDS)` — if the audio is shorter, the slide simply sits on screen a little longer after the audio ends. No harm; nothing to flag.

**Ceiling (soft target, not a hard clamp):** Clamping display time *down* to 12s when narration runs longer was explicitly ruled out — it would either cut the audio off mid-sentence or let it bleed into the next slide's visuals, and neither is acceptable. So 12s is enforced in two layers instead of one hard clamp:

1. **Upstream (primary defense):** the narration-generation prompt in `script_generator.py` now requires narration to be "speakable in under 12 seconds at a natural pace — roughly 30 words or fewer, 1–2 short sentences." At typical TTS speaking rates (~140–160 wpm), 30 words is ~11–13s, so this keeps the vast majority of slides comfortably under the ceiling by construction, rather than trying to fix it after the fact.
2. **Downstream (safety net):** if a slide's real audio duration still exceeds 12s despite the prompt constraint, `tts_generator.py` logs a warning (`logger.warning(...)`, includes `file_id` and the slide index) so it's visible in backend logs as a data-quality signal — this is the same kind of diagnostic-tagging instinct behind the separately-planned eval improvement. At render time, that slide's display duration is simply `duration_seconds` (unclamped, no `min()` against the ceiling) — the slide runs long, but audio and visuals stay in sync and nothing is cut off. This should be rare in practice; if backend logs show it happening often, the fix is to tighten the prompt's word-count guidance further, not to change the render-time behavior.

Net effect: `displayFrames = ceil(max(duration_seconds, MIN_SLIDE_SECONDS) * FPS)` — the ceiling never appears in this formula. It's a prompt-side target and a monitoring threshold, not a runtime clamp.

---

## 6. Schema Changes

**Persisted `{file_id}_script.json`** (written by `_run_generate`, read by `/quiz`, `/eval`, and as the basis for render props) — each slide gains `audio_path` and `duration_seconds`:

```json
{
  "file_id": "abc-123",
  "title": "...",
  "slides": [
    {
      "index": 0,
      "title": "...",
      "narration": "...",
      "bullets": ["...", "..."],
      "audio_path": "C:\\...\\backend\\uploads\\abc-123\\audio\\slide_0.mp3",
      "duration_seconds": 4.87
    }
  ]
}
```

**Ephemeral render props** (`render/out/{render_job_id}_props.json`, built fresh per render job by `_build_render_props`, never the source of truth — gitignored like the rest of `render/out/`): every field above, plus `audio_static_path`, a `staticFile()`-relative string pointing at a copy of the audio placed under `render/public/`:

```json
{
  "file_id": "abc-123",
  "title": "...",
  "slides": [
    {
      "index": 0,
      "title": "...",
      "narration": "...",
      "bullets": ["...", "..."],
      "audio_path": "C:\\...\\slide_0.mp3",
      "duration_seconds": 4.87,
      "audio_static_path": "audio/<render_job_id>/slide_0.mp3"
    }
  ]
}
```

Two path fields exist because they serve different processes: `audio_path` is a real filesystem path the *Python backend* can copy from; `audio_static_path` is a `remotion`-relative asset key the *Remotion/Node process* resolves via `staticFile()`. Neither works for the other's purpose.

---

## 7. Why Copy Into `render/public/` Instead of Passing `audio_path` Straight Through

Remotion's documented way to serve local files to a composition is to place them under the project's `public/` folder and reference them with `staticFile('relative/path.mp3')` — arbitrary filesystem paths outside `public/` aren't guaranteed servable to the browser context Remotion renders in. Since generated audio lives under `backend/uploads/{file_id}/audio/`, outside `render/public/`, `_build_render_props` copies each slide's MP3 into `render/public/audio/{render_job_id}/slide_{index}.mp3` right before invoking the renderer, and points `audio_static_path` at that copy.

This sidesteps the existing Windows→WSL2 path-translation logic entirely for audio: `_wsl_path()` is still needed for `cwd`, the props file path, and the output path (as it is today), but `audio_static_path` is a plain relative string with no OS-specific path in it — Remotion resolves it against its own `public/` folder from inside whichever process (Windows or WSL) actually runs the render, so it needs no translation.

`render/public/` doesn't exist yet in the repo; it's created on demand (`mkdir(parents=True, exist_ok=True)`) the first time a render runs, the same way `render/out/` already is.

---

## 8. Remotion Composition Changes

`LearnFlowVideo.tsx` moves from "one global `useCurrentFrame()` divided by a fixed interval" to "one `<Sequence>` per slide with its own duration," each wrapping both the visual (`<Slide>`) and its audio (`<Audio>`):

```tsx
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
      {slides.map((slide) => {
        const durationInFrames = slideDurationInFrames(slide)
        const from = cursor
        cursor += durationInFrames
        return (
          <Sequence key={slide.index} from={from} durationInFrames={durationInFrames}>
            <Slide slide={slide} />
            <Audio src={staticFile(slide.audio_static_path)} />
          </Sequence>
        )
      })}
    </>
  )
}
```

`Root.tsx`'s `calculateMetadata` sums real per-slide frame counts instead of `slides.length * FRAMES_PER_SLIDE`:

```tsx
const calculateMetadata: CalculateMetadataFunction<VideoProps> = ({ props }) => ({
  durationInFrames: props.slides.reduce((sum, s) => sum + slideDurationInFrames(s), 0)
    || Math.ceil(MIN_SLIDE_SECONDS * FPS),
})
```

Field names on `SlideData` stay snake_case (`audio_static_path`, `duration_seconds`) rather than being converted to camelCase, because they arrive verbatim from the JSON `--props` file with no serialization layer in between — matching how `narration`/`bullets`/`title`/`index` already pass through unchanged today.

`MAX_SLIDE_SECONDS` does not appear on the TypeScript side at all — per §5, it's a prompt-side/monitoring constant only, not a render-time clamp.

---

## 9. Where TTS Fits in the Pipeline

**Decision: bundle TTS into the existing `_run_generate` background task, immediately after `generate_script()` succeeds, before the script JSON is written to disk.** Do not add a separate step, job type, or frontend polling state.

Why this is simpler than a separate step, given the actual constraint ("render needs audio to exist before it starts"):

- `/render/{job_id}` already refuses to start unless `jobs[job_id]["status"] == "complete"`. If TTS synthesis is part of what makes a `/generate` job "complete," that existing gate is already sufficient — audio is guaranteed to exist by the time `/render` can be called. **No change to the render trigger point, and no change needed in the frontend's existing "wait for generate to complete, then call /render" flow.**
- A separate TTS step would need its own job state, its own "is this job's audio ready" check wired into the render gate, and a new frontend poll — all to re-derive a guarantee the existing `status == "complete"` check already gives for free once TTS lives inside `_run_generate`.
- Error handling is uniform for free: `_run_generate`'s existing `try: ... except Exception as exc: jobs[job_id] = {"status": "error", ...}` already wraps `generate_script()`. Adding the `synthesize_slide_audio()` call inside that same `try` block means a missing `ELEVENLABS_API_KEY` or an ElevenLabs API failure fails the job exactly the way a missing `ANTHROPIC_API_KEY` already does today — same mechanism, same shape, nothing new to test conceptually.

Trade-off accepted: a `/generate` job now takes longer wall-clock time (one Claude call + N sequential ElevenLabs calls, one per slide, typically 5–8) before flipping to `"complete"`. Given the existing UI already shows a "Processing" step while polling `/job/{job_id}`, this is a duration change, not a UX change — no new state to display.

---

## 10. Out of Scope

- Voice selection UI (README already excludes this from MVP scope)
- Parallelizing per-slide ElevenLabs calls (sequential is simpler and the job already runs as a background task; revisit only if generate latency becomes a real problem)
- Re-encoding or normalizing audio loudness across slides
- Deleting/cleaning up old `render/public/audio/{render_job_id}/` directories after a render completes (matches existing behavior: `render/out/*.mp4` isn't cleaned up either)
