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
    for i, slide in enumerate(slides):
        audio_path = audio_dir / f"slide_{i}.mp3"
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
