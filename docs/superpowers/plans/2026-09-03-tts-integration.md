# TTS Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire ElevenLabs TTS into the pipeline end-to-end — each slide's narration is synthesized to an MP3, its real duration drives that slide's on-screen time (bounded), and the Remotion composition plays audio in sync with visuals instead of rendering silent fixed-length slides.

**Architecture:** A new `backend/tts_generator.py` module synthesizes one MP3 per slide via ElevenLabs and reads its real duration with `mutagen`. `_run_generate` (in `backend/main.py`) calls it right after `generate_script()`, so a `/generate` job's `"complete"` status means text *and* audio are both ready — no new job state, no change to the existing `/render` gate. At render time, `_run_remotion_render` copies each slide's audio into `render/public/` (Remotion's servable-assets convention) and builds an ephemeral props file carrying a `staticFile()`-relative path per slide. `LearnFlowVideo.tsx` switches from one fixed-interval frame calculation to a `<Sequence>` per slide with its own duration, each pairing `<Slide>` with `<Audio>`.

**Tech Stack:** `elevenlabs` (Python SDK, already in `requirements.txt` but unused), `mutagen` (new), FastAPI background tasks, Remotion `Audio`/`Sequence`/`staticFile` (all from the core `remotion` package, already installed), pytest + `unittest.mock`.

**Spec:** `docs/superpowers/specs/2026-09-03-tts-integration-design.md`

## Global Constraints

- `MIN_SLIDE_SECONDS = 3.0` — hard floor, defined in both `backend/tts_generator.py` and `render/src/LearnFlowVideo.tsx`
- `MAX_SLIDE_SECONDS = 12.0` — soft ceiling, defined only in `backend/tts_generator.py`; used solely to log a warning, never to clamp render-time duration down (see spec §5)
- `DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"`, overridable via `ELEVENLABS_VOICE_ID` env var
- ElevenLabs call shape: `client.text_to_speech.convert(voice_id=..., text=..., model_id="eleven_multilingual_v2", output_format="mp3_44100_128")` → `Iterator[bytes]`
- Missing `ELEVENLABS_API_KEY` → `raise ValueError("ELEVENLABS_API_KEY environment variable is not set")`, checked before any network call — mirrors `generate_script`'s existing `ANTHROPIC_API_KEY` check
- Audio file layout: `{uploads_dir}/{file_id}/audio/slide_{index}.mp3`
- Render-time public copy: `render/public/audio/{render_job_id}/slide_{index}.mp3`, referenced as `staticFile(f"audio/{render_job_id}/slide_{index}.mp3")`
- Render-time ephemeral props file: `render/out/{render_job_id}_props.json` (same directory as the output `.mp4`, already gitignored via `render/out/`)
- FPS = 30 (existing, from `Root.tsx`)
- `SlideData` field names stay snake_case (`audio_static_path`, `duration_seconds`) — no camelCase conversion layer, matching existing fields (`narration`, `bullets`)

---

### Task 1: TTS synthesis module

**Files:**
- Create: `backend/tts_generator.py`
- Create: `backend/tests/test_tts_generator.py`
- Modify: `backend/requirements.txt`

**Interfaces:**
- Produces:
  - `synthesize_slide_audio(file_id: str, slides: list[dict], uploads_dir: pathlib.Path) -> list[dict]` — each returned slide dict is the input slide plus `audio_path: str` and `duration_seconds: float`
  - `MIN_SLIDE_SECONDS: float = 3.0`, `MAX_SLIDE_SECONDS: float = 12.0` module-level constants

---

- [ ] **Step 1: Add `mutagen` to `backend/requirements.txt`**

```
fastapi
uvicorn[standard]
anthropic
elevenlabs
mutagen
pdfplumber
python-multipart
```

```bash
cd backend && pip install mutagen
```

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_tts_generator.py`:

```python
import logging

import pytest

from tts_generator import MAX_SLIDE_SECONDS, synthesize_slide_audio

SLIDES = [
    {"index": 0, "title": "Intro", "narration": "Hello there.", "bullets": ["A"]},
    {"index": 1, "title": "Middle", "narration": "More narration.", "bullets": ["B"]},
]


class FakeTextToSpeech:
    def __init__(self, convert_fn):
        self.convert = convert_fn


class FakeClient:
    def __init__(self, convert_fn):
        self._convert_fn = convert_fn
        self.text_to_speech = FakeTextToSpeech(convert_fn)

    def __call__(self, api_key):
        self.api_key = api_key
        return self


def test_missing_api_key_raises_value_error(tmp_path, monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    with pytest.raises(ValueError, match="ELEVENLABS_API_KEY"):
        synthesize_slide_audio("file-1", SLIDES, tmp_path)


def test_synthesizes_audio_for_each_slide(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    monkeypatch.setattr("tts_generator._get_duration_seconds", lambda path: 4.2)

    calls = []

    def fake_convert(**kwargs):
        calls.append(kwargs)
        return [b"fake", b"mp3", b"bytes"]

    monkeypatch.setattr("tts_generator.ElevenLabs", FakeClient(fake_convert))

    result = synthesize_slide_audio("file-1", SLIDES, tmp_path)

    assert len(result) == 2
    for i, slide in enumerate(result):
        expected_path = tmp_path / "file-1" / "audio" / f"slide_{i}.mp3"
        assert expected_path.exists()
        assert expected_path.read_bytes() == b"fakemp3bytes"
        assert slide["audio_path"] == str(expected_path.resolve())
        assert slide["duration_seconds"] == 4.2
        assert slide["narration"] == SLIDES[i]["narration"]
        assert slide["title"] == SLIDES[i]["title"]
        assert slide["index"] == i

    assert calls[0]["voice_id"]
    assert calls[0]["text"] == "Hello there."
    assert calls[0]["model_id"] == "eleven_multilingual_v2"
    assert calls[0]["output_format"] == "mp3_44100_128"


def test_uses_voice_id_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "custom-voice-id")
    monkeypatch.setattr("tts_generator._get_duration_seconds", lambda path: 4.2)

    calls = []

    def fake_convert(**kwargs):
        calls.append(kwargs)
        return [b"bytes"]

    monkeypatch.setattr("tts_generator.ElevenLabs", FakeClient(fake_convert))

    synthesize_slide_audio("file-1", SLIDES[:1], tmp_path)

    assert calls[0]["voice_id"] == "custom-voice-id"


def test_flags_slide_exceeding_ceiling(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    monkeypatch.setattr("tts_generator._get_duration_seconds", lambda path: 15.0)
    monkeypatch.setattr("tts_generator.ElevenLabs", FakeClient(lambda **kwargs: [b"bytes"]))

    with caplog.at_level(logging.WARNING):
        result = synthesize_slide_audio("file-1", SLIDES[:1], tmp_path)

    assert result[0]["duration_seconds"] == 15.0
    assert any("exceeding" in record.message for record in caplog.records)
    assert MAX_SLIDE_SECONDS == 12.0


def test_does_not_flag_slide_within_ceiling(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    monkeypatch.setattr("tts_generator._get_duration_seconds", lambda path: 8.0)
    monkeypatch.setattr("tts_generator.ElevenLabs", FakeClient(lambda **kwargs: [b"bytes"]))

    with caplog.at_level(logging.WARNING):
        synthesize_slide_audio("file-1", SLIDES[:1], tmp_path)

    assert len(caplog.records) == 0
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
cd backend && python -m pytest tests/test_tts_generator.py -v
```

Expected: `ModuleNotFoundError: No module named 'tts_generator'`

- [ ] **Step 4: Create `backend/tts_generator.py`**

```python
import logging
import os
import pathlib

from elevenlabs.client import ElevenLabs
from mutagen.mp3 import MP3

logger = logging.getLogger(__name__)

DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"
MODEL_ID = "eleven_multilingual_v2"
OUTPUT_FORMAT = "mp3_44100_128"

MIN_SLIDE_SECONDS = 3.0
MAX_SLIDE_SECONDS = 12.0


def synthesize_slide_audio(file_id: str, slides: list[dict], uploads_dir: pathlib.Path) -> list[dict]:
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise ValueError("ELEVENLABS_API_KEY environment variable is not set")

    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)
    client = ElevenLabs(api_key=api_key)
    audio_dir = uploads_dir / file_id / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    annotated_slides = []
    for slide in slides:
        audio_path = audio_dir / f"slide_{slide['index']}.mp3"
        chunks = client.text_to_speech.convert(
            voice_id=voice_id,
            text=slide["narration"],
            model_id=MODEL_ID,
            output_format=OUTPUT_FORMAT,
        )
        audio_path.write_bytes(b"".join(chunks))

        duration_seconds = _get_duration_seconds(audio_path)
        if duration_seconds > MAX_SLIDE_SECONDS:
            logger.warning(
                "Slide %d narration audio is %.1fs, exceeding the %.0fs pacing target "
                "(file_id=%s). Display duration will be extended to match rather than cut off.",
                slide["index"], duration_seconds, MAX_SLIDE_SECONDS, file_id,
            )

        annotated_slides.append({
            **slide,
            "audio_path": str(audio_path.resolve()),
            "duration_seconds": duration_seconds,
        })

    return annotated_slides


def _get_duration_seconds(audio_path: pathlib.Path) -> float:
    return MP3(str(audio_path)).info.length
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
cd backend && python -m pytest tests/test_tts_generator.py -v
```

Expected: 5 tests PASSED

- [ ] **Step 6: Commit**

```bash
git add backend/tts_generator.py backend/tests/test_tts_generator.py backend/requirements.txt
git commit -m "feat: add ElevenLabs TTS synthesis module"
```

---

### Task 2: Cap spoken narration length in the generation prompt

**Files:**
- Modify: `backend/script_generator.py`
- Modify: `backend/tests/test_script_generator.py`

**Interfaces:**
- Consumes: none new
- Produces: no signature changes — `generate_script` and `_USER_TEMPLATE` behavior only

---

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_script_generator.py`:

```python
from script_generator import _USER_TEMPLATE


def test_user_template_caps_narration_speaking_length():
    assert "12 seconds" in _USER_TEMPLATE
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd backend && python -m pytest tests/test_script_generator.py::test_user_template_caps_narration_speaking_length -v
```

Expected: FAIL (assert "12 seconds" in ...) — not present yet

- [ ] **Step 3: Update `_USER_TEMPLATE` in `backend/script_generator.py`**

Change the `narration` schema field description and add a rule. Full updated template:

```python
_USER_TEMPLATE = """\
Source text:
{text}

Produce a JSON object with this exact schema:
{{
  "title": "<overall document title>",
  "slides": [
    {{
      "index": <int starting at 0>,
      "title": "<slide title>",
      "narration": "<1-2 short sentences suitable for text-to-speech, speakable in under 12 seconds>",
      "bullets": ["<key point>", ...]
    }}
  ]
}}

Rules:
- Generate between 5 and 8 slides.
- Each slide must have 2 to 4 bullets.
- Narration must be complete sentences, not bullet points.
- Narration must be speakable in under 12 seconds at a natural pace — roughly 30 words or fewer. Prefer a single sentence; use two only if both are short.
- Return only the JSON object. No markdown, no explanation.\
"""
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd backend && python -m pytest tests/test_script_generator.py -v
```

Expected: all tests PASSED (existing + 1 new)

- [ ] **Step 5: Commit**

```bash
git add backend/script_generator.py backend/tests/test_script_generator.py
git commit -m "feat: cap narration speaking length to fit slide pacing"
```

---

### Task 3: Wire TTS into the `/generate` background task

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/tests/test_routes.py`

**Interfaces:**
- Consumes: `synthesize_slide_audio(file_id, slides, uploads_dir) -> list[dict]` (Task 1)
- Produces: `_run_generate`'s job `result` now includes `audio_path`/`duration_seconds` per slide when status is `"complete"`

---

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_routes.py`, in the `/generate` section:

```python
def test_generate_job_merges_tts_audio_into_slides(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "UPLOADS_DIR", tmp_path)
    (tmp_path / "abc-123.pdf").write_bytes(b"%PDF-1.4")

    script_result = {
        "file_id": "abc-123",
        "title": "T",
        "slides": [{"index": 0, "title": "S1", "narration": "Hi.", "bullets": ["A"]}],
    }
    audio_annotated = [
        {**script_result["slides"][0], "audio_path": "/fake/slide_0.mp3", "duration_seconds": 4.5},
    ]

    with patch("main.extract_text", return_value="text content"), \
         patch("main.generate_script", return_value=script_result), \
         patch("main.synthesize_slide_audio", return_value=audio_annotated) as mock_tts:
        gen = client.post("/generate/abc-123")

    job_id = gen.json()["job_id"]
    status = client.get(f"/job/{job_id}")
    body = status.json()

    assert body["status"] == "complete"
    assert body["result"]["slides"][0]["audio_path"] == "/fake/slide_0.mp3"
    assert body["result"]["slides"][0]["duration_seconds"] == 4.5
    mock_tts.assert_called_once_with("abc-123", script_result["slides"], tmp_path)


def test_generate_job_fails_when_tts_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "UPLOADS_DIR", tmp_path)
    (tmp_path / "abc-123.pdf").write_bytes(b"%PDF-1.4")

    script_result = {"file_id": "abc-123", "title": "T", "slides": []}

    with patch("main.extract_text", return_value="text content"), \
         patch("main.generate_script", return_value=script_result), \
         patch("main.synthesize_slide_audio", side_effect=ValueError("ELEVENLABS_API_KEY environment variable is not set")):
        gen = client.post("/generate/abc-123")

    job_id = gen.json()["job_id"]
    status = client.get(f"/job/{job_id}")
    body = status.json()

    assert body["status"] == "error"
    assert "ELEVENLABS_API_KEY" in body["error"]
    assert body["result"] is None
```

Then update the two existing `/generate` tests that patch `main.generate_script` but don't yet account for the new `synthesize_slide_audio` call — without a patch, they'd now fail because `ELEVENLABS_API_KEY` isn't set in the test environment. Change `test_generate_returns_job_id` and `test_job_status_reflects_background_task_result` to also patch it:

```python
def test_generate_returns_job_id(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "UPLOADS_DIR", tmp_path)
    (tmp_path / "abc-123.pdf").write_bytes(b"%PDF-1.4")

    script_result = {"file_id": "abc-123", "title": "T", "slides": []}
    with patch("main.extract_text", return_value="text content"), \
         patch("main.generate_script", return_value=script_result), \
         patch("main.synthesize_slide_audio", return_value=[]):
        response = client.post("/generate/abc-123")

    assert response.status_code == 200
    assert "job_id" in response.json()


def test_job_status_reflects_background_task_result(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "UPLOADS_DIR", tmp_path)
    (tmp_path / "abc-123.pdf").write_bytes(b"%PDF-1.4")

    script_result = {"file_id": "abc-123", "title": "Test", "slides": []}
    with patch("main.extract_text", return_value="text"), \
         patch("main.generate_script", return_value=script_result), \
         patch("main.synthesize_slide_audio", return_value=[]):
        gen = client.post("/generate/abc-123")

    job_id = gen.json()["job_id"]
    status = client.get(f"/job/{job_id}")
    assert status.status_code == 200
    body = status.json()
    assert body["job_id"] == job_id
    # TestClient runs background tasks synchronously, so status is "complete"
    assert body["status"] == "complete"
    assert body["result"]["title"] == "Test"
    assert body["error"] is None
```

`test_job_captures_generate_error` (the existing Claude-failure test) needs no change — `generate_script` raising means `synthesize_slide_audio` is never reached.

- [ ] **Step 2: Run tests to confirm the new ones fail**

```bash
cd backend && python -m pytest tests/test_routes.py -v
```

Expected: `test_generate_job_merges_tts_audio_into_slides` and `test_generate_job_fails_when_tts_raises` FAIL (`AttributeError`/`ModuleNotFoundError`-style — `main.synthesize_slide_audio` doesn't exist to patch yet). The two updated existing tests should still PASS at this point since `ELEVENLABS_API_KEY` isn't called yet in `main.py`.

- [ ] **Step 3: Wire TTS into `backend/main.py`**

Add the import (with the other local module imports near the top):

```python
from tts_generator import synthesize_slide_audio
```

Update `_run_generate`:

```python
def _run_generate(job_id: str, file_id: str, pdf_path: pathlib.Path) -> None:
    jobs[job_id]["status"] = "running"
    try:
        text = extract_text(pdf_path)
        script = generate_script(file_id, text)
        script["slides"] = synthesize_slide_audio(file_id, script["slides"], UPLOADS_DIR)
        script_path = pdf_path.parent / f"{file_id}_script.json"
        script_path.write_text(json.dumps(script))
        jobs[job_id] = {"status": "complete", "result": script, "error": None}
    except Exception as exc:
        jobs[job_id] = {"status": "error", "result": None, "error": str(exc)}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd backend && python -m pytest tests/test_routes.py -v
```

Expected: all tests PASSED

- [ ] **Step 5: Run the full backend test suite to confirm no regressions**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: all tests PASSED (existing suite + new TTS tests)

- [ ] **Step 6: Commit**

```bash
git add backend/main.py backend/tests/test_routes.py
git commit -m "feat: synthesize narration audio as part of the generate job"
```

---

### Task 4: Copy slide audio into `render/public/` and build ephemeral render props

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/tests/test_render_route.py`

**Interfaces:**
- Consumes: `slide["audio_path"]` (absolute filesystem path, Task 1/3)
- Produces: `_build_render_props(script: dict, render_job_id: str) -> dict` — same shape as `script`, each slide additionally carrying `audio_static_path: str`; also produces the side effect of populating `render/public/audio/{render_job_id}/`

---

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_render_route.py`, update `_seed_complete_generate_job` to include a real audio file and the new fields, and add a new test for the copy behavior:

```python
def _seed_complete_generate_job(tmp_path: pathlib.Path, file_id: str = "abc-123") -> str:
    """Insert a complete generate job into `jobs` and write its script JSON to disk."""
    audio_dir = tmp_path / file_id / "audio"
    audio_dir.mkdir(parents=True)
    audio_path = audio_dir / "slide_0.mp3"
    audio_path.write_bytes(b"fake mp3 bytes")

    script = {
        "file_id": file_id,
        "title": "Test Doc",
        "slides": [
            {
                "index": 0,
                "title": "Introduction",
                "narration": "Intro narration.",
                "bullets": ["Point A", "Point B"],
                "audio_path": str(audio_path.resolve()),
                "duration_seconds": 4.2,
            }
        ],
    }
    (tmp_path / f"{file_id}_script.json").write_text(json.dumps(script))
    job_id = "generate-job-001"
    jobs[job_id] = {"status": "complete", "result": script, "error": None}
    return job_id


# ── Render-time audio props ──────────────────────────────────────────────────

def test_render_copies_slide_audio_and_builds_static_path(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "UPLOADS_DIR", tmp_path)
    job_id = _seed_complete_generate_job(tmp_path)

    with patch("main.subprocess.run", return_value=_mock_subprocess(0)):
        gen = client.post(f"/render/{job_id}")

    render_job_id = gen.json()["job_id"]

    copied_audio = main._RENDER_DIR / "public" / "audio" / render_job_id / "slide_0.mp3"
    assert copied_audio.exists()
    assert copied_audio.read_bytes() == b"fake mp3 bytes"

    props_path = main._RENDER_DIR / "out" / f"{render_job_id}_props.json"
    assert props_path.exists()
    props = json.loads(props_path.read_text())
    assert props["slides"][0]["audio_static_path"] == f"audio/{render_job_id}/slide_0.mp3"
    assert props["slides"][0]["duration_seconds"] == 4.2

    # cleanup so repeated test runs don't accumulate fixtures under render/
    copied_audio.unlink()
    props_path.unlink()
```

- [ ] **Step 2: Run tests to confirm the new one fails, existing ones still pass**

```bash
cd backend && python -m pytest tests/test_render_route.py -v
```

Expected: `test_render_copies_slide_audio_and_builds_static_path` FAILS (`AttributeError: module 'main' has no attribute '_build_render_props'` or the copied file/props simply don't exist). Other render tests should still PASS — they don't inspect `render/public/` and the mocked `subprocess.run` means the existing `props_path`/`out_path` logic still runs.

- [ ] **Step 3: Add `_build_render_props` and wire it into `_run_remotion_render` in `backend/main.py`**

Add `import shutil` near the other stdlib imports. Add the new function and update `_run_remotion_render`:

```python
def _build_render_props(script: dict, render_job_id: str) -> dict:
    """Copy each slide's audio into render/public/ and return props with a staticFile-relative path per slide."""
    audio_dest_dir = _RENDER_DIR / "public" / "audio" / render_job_id
    audio_dest_dir.mkdir(parents=True, exist_ok=True)

    slides = []
    for slide in script["slides"]:
        dest = audio_dest_dir / f"slide_{slide['index']}.mp3"
        shutil.copy(slide["audio_path"], dest)
        slides.append({
            **slide,
            "audio_static_path": f"audio/{render_job_id}/slide_{slide['index']}.mp3",
        })
    return {**script, "slides": slides}


def _run_remotion_render(render_job_id: str, script: dict) -> None:
    jobs[render_job_id]["status"] = "running"
    try:
        render_props = _build_render_props(script, render_job_id)
        props_path = (_RENDER_DIR / "out" / f"{render_job_id}_props.json").resolve()
        props_path.parent.mkdir(parents=True, exist_ok=True)
        props_path.write_text(json.dumps(render_props))

        out_path = (_RENDER_DIR / "out" / f"{render_job_id}.mp4").resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if sys.platform == "win32":
            # On Windows ARM, Chrome Headless Shell is unavailable.
            # Route the render through WSL2 (Ubuntu) where the linux-arm64
            # Chromium binary works correctly.
            wsl_props = _wsl_path(props_path)
            wsl_out = _wsl_path(out_path)
            wsl_render_dir = _wsl_path(_RENDER_DIR)
            nvm_init = ". /home/srikarvan/.nvm/nvm.sh"
            render_cmd = (
                f"{nvm_init} && "
                f"cd {shlex.quote(wsl_render_dir)} && "
                f"npx remotion render src/index.ts LearnFlowVideo {shlex.quote(wsl_out)} "
                f"--props={shlex.quote(wsl_props)}"
            )
            cmd = ["wsl", "-d", "Ubuntu", "--", "bash", "-c", render_cmd]
            cwd = None  # WSL cd is handled in the shell command
        else:
            cmd = [
                "npx", "remotion", "render",
                "src/index.ts",
                "LearnFlowVideo",
                str(out_path),
                "--props", str(props_path),
            ]
            cwd = str(_RENDER_DIR)

        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            jobs[render_job_id] = {
                "status": "complete",
                "result": {"video_path": str(out_path)},
                "error": None,
            }
        else:
            jobs[render_job_id] = {
                "status": "error",
                "result": None,
                "error": result.stderr.decode("utf-8", errors="replace"),
            }
    except Exception as exc:
        jobs[render_job_id] = {"status": "error", "result": None, "error": str(exc)}
```

This replaces the previous `props_path = (UPLOADS_DIR / f"{file_id}_script.json").resolve()` line — the render now always uses the freshly-built ephemeral props file, never the persisted `{file_id}_script.json` directly, since only the ephemeral one has `audio_static_path`.

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd backend && python -m pytest tests/test_render_route.py -v
```

Expected: all tests PASSED

- [ ] **Step 5: Run the full backend test suite to confirm no regressions**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: all tests PASSED

- [ ] **Step 6: Commit**

```bash
git add backend/main.py backend/tests/test_render_route.py
git commit -m "feat: copy slide audio into render/public and build ephemeral render props"
```

---

### Task 5: Variable-duration Remotion composition with synced audio

**Files:**
- Modify: `render/src/LearnFlowVideo.tsx`
- Modify: `render/src/Root.tsx`

**Interfaces:**
- Consumes: `slide.audio_static_path` and `slide.duration_seconds` (Task 4)
- Produces: `slideDurationInFrames(slide: SlideData): number`, `FPS: number`, `MIN_SLIDE_SECONDS: number` (all exported from `LearnFlowVideo.tsx`, imported by `Root.tsx`)

---

- [ ] **Step 1: Replace `render/src/LearnFlowVideo.tsx`**

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

- [ ] **Step 2: Replace `render/src/Root.tsx`**

```tsx
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
```

Note: `defaultProps.slides[0].audio_static_path` is `''`, which means `staticFile('')` would be invoked if this default were ever actually rendered — it isn't: `defaultProps` only backs the Remotion Studio preview UI before real props are supplied, and every real invocation (both `/render`'s subprocess call and Remotion Studio once a composition is selected with real `--props`) supplies actual slide data with a real path.

- [ ] **Step 3: Type-check to verify it compiles**

```bash
cd render && npx tsc --noEmit
```

Expected: no errors, exits 0.

- [ ] **Step 4: Manually verify in Remotion Studio**

```bash
cd render && npx remotion studio src/index.ts
```

Open the `LearnFlowVideo` composition, and using the props editor panel, paste in a real render-time props JSON produced by a prior `/render` call (e.g. `render/out/<some-render-job-id>_props.json` from a manual backend test run) — or, if none exists yet, come back to this step after Task 4's test run has produced one under `render/out/`. Confirm: each slide's duration on the timeline visibly varies (not a uniform 5s block), and scrubbing through a slide plays its narration audio in sync with that slide's visual.

- [ ] **Step 5: Commit**

```bash
git add render/src/LearnFlowVideo.tsx render/src/Root.tsx
git commit -m "feat: sync Remotion slide duration and audio to real narration length"
```

---

## Post-Plan Verification

After all five tasks are committed, run an actual end-to-end `/generate` → `/render` cycle (not mocked) with both `ANTHROPIC_API_KEY` and `ELEVENLABS_API_KEY` set, on a real uploaded PDF, and play the resulting `.mp4`. This plan's unit tests mock both external APIs by design (per existing project convention — see `test_render_route.py`'s `subprocess.run` mocking) and cannot catch a real ElevenLabs response-shape mismatch, an invalid voice ID, or an actual audio/video desync. Confirm at minimum: narration audio is audible, slide changes line up with sentence boundaries, and no slide's audio is cut off or bleeds into the next slide.
