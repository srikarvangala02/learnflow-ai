import logging

import pytest

from tts_generator import DEFAULT_VOICE_ID, MAX_SLIDE_SECONDS, synthesize_slide_audio

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

    assert calls[0]["voice_id"] == DEFAULT_VOICE_ID
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
