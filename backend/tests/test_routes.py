import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import main
from main import app, jobs

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_state(tmp_path, monkeypatch):
    jobs.clear()
    monkeypatch.setattr(main, "UPLOADS_DIR", tmp_path)
    yield
    jobs.clear()


# ── /upload ──────────────────────────────────────────────────────────────────

def test_upload_pdf_returns_file_id():
    response = client.post(
        "/upload",
        files={"file": ("test.pdf", io.BytesIO(b"%PDF-1.4 minimal"), "application/pdf")},
    )
    assert response.status_code == 200
    body = response.json()
    assert "file_id" in body
    assert len(body["file_id"]) == 36  # UUID format


def test_upload_non_pdf_returns_400():
    response = client.post(
        "/upload",
        files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


def test_upload_file_over_20mb_returns_400():
    big = b"A" * (21 * 1024 * 1024)
    response = client.post(
        "/upload",
        files={"file": ("big.pdf", io.BytesIO(big), "application/pdf")},
    )
    assert response.status_code == 400
    assert "20 MB" in response.json()["detail"]


# ── /generate ────────────────────────────────────────────────────────────────

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


def test_generate_unknown_file_id_returns_404():
    response = client.post("/generate/nonexistent-file-id")
    assert response.status_code == 404


def test_generate_job_merges_tts_audio_into_slides(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "UPLOADS_DIR", tmp_path)
    (tmp_path / "abc-123.pdf").write_bytes(b"%PDF-1.4")

    script_result = {
        "file_id": "abc-123",
        "title": "T",
        "slides": [{"index": 0, "title": "S1", "narration": "Hi.", "bullets": ["A"]}],
    }
    # Captured before the request runs: `generate_script` is mocked to return
    # `script_result` itself (no copy), and `_run_generate` reassigns
    # `script["slides"]` in place, which mutates `script_result` too. Reading
    # `script_result["slides"]` after the call would see the post-mutation
    # (audio-annotated) value instead of what was actually passed in.
    original_slides = script_result["slides"]
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
    mock_tts.assert_called_once_with("abc-123", original_slides, tmp_path)


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


# ── /job ─────────────────────────────────────────────────────────────────────

def test_job_status_unknown_returns_404():
    response = client.get("/job/does-not-exist")
    assert response.status_code == 404


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


def test_job_captures_generate_error(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "UPLOADS_DIR", tmp_path)
    (tmp_path / "abc-123.pdf").write_bytes(b"%PDF-1.4")

    with patch("main.extract_text", return_value="text"), \
         patch("main.generate_script", side_effect=ValueError("ANTHROPIC_API_KEY environment variable is not set")):
        gen = client.post("/generate/abc-123")

    job_id = gen.json()["job_id"]
    status = client.get(f"/job/{job_id}")
    body = status.json()
    assert body["status"] == "error"
    assert "ANTHROPIC_API_KEY" in body["error"]
    assert body["result"] is None
