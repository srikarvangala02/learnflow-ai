import json
import pathlib
from unittest.mock import MagicMock, patch

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


def _seed_complete_generate_job(tmp_path: pathlib.Path, file_id: str = "abc-123") -> str:
    """Insert a complete generate job into `jobs` and write its script JSON to disk."""
    script = {
        "file_id": file_id,
        "title": "Test Doc",
        "slides": [
            {
                "index": 0,
                "title": "Introduction",
                "narration": "Intro narration.",
                "bullets": ["Point A", "Point B"],
            }
        ],
    }
    (tmp_path / f"{file_id}_script.json").write_text(json.dumps(script))
    job_id = "generate-job-001"
    jobs[job_id] = {"status": "complete", "result": script, "error": None}
    return job_id


def _mock_subprocess(returncode: int = 0, stderr: bytes = b"") -> MagicMock:
    m = MagicMock()
    m.returncode = returncode
    m.stderr = stderr
    return m


# ── POST /render/{job_id} ────────────────────────────────────────────────────

def test_render_returns_job_id(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "UPLOADS_DIR", tmp_path)
    job_id = _seed_complete_generate_job(tmp_path)

    with patch("main.subprocess.run", return_value=_mock_subprocess(0)):
        response = client.post(f"/render/{job_id}")

    assert response.status_code == 200
    body = response.json()
    assert "job_id" in body
    assert len(body["job_id"]) == 36  # UUID format


def test_render_unknown_job_returns_404():
    response = client.post("/render/does-not-exist")
    assert response.status_code == 404


def test_render_incomplete_job_returns_400(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "UPLOADS_DIR", tmp_path)
    jobs["pending-job"] = {"status": "pending", "result": None, "error": None}
    response = client.post("/render/pending-job")
    assert response.status_code == 400
    assert "complete" in response.json()["detail"].lower()


def test_render_error_job_returns_400(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "UPLOADS_DIR", tmp_path)
    jobs["error-job"] = {"status": "error", "result": None, "error": "Claude failed"}
    response = client.post("/render/error-job")
    assert response.status_code == 400


# ── Background task outcomes ─────────────────────────────────────────────────

def test_successful_render_sets_job_complete(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "UPLOADS_DIR", tmp_path)
    job_id = _seed_complete_generate_job(tmp_path)

    with patch("main.subprocess.run", return_value=_mock_subprocess(0)):
        gen = client.post(f"/render/{job_id}")

    render_job_id = gen.json()["job_id"]
    status = client.get(f"/job/{render_job_id}")
    assert status.status_code == 200
    body = status.json()
    assert body["status"] == "complete"
    assert "video_path" in body["result"]
    assert body["result"]["video_path"].endswith(".mp4")
    assert body["error"] is None


def test_failed_render_sets_job_error(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "UPLOADS_DIR", tmp_path)
    job_id = _seed_complete_generate_job(tmp_path)

    with patch("main.subprocess.run", return_value=_mock_subprocess(1, b"npx: command not found")):
        gen = client.post(f"/render/{job_id}")

    render_job_id = gen.json()["job_id"]
    status = client.get(f"/job/{render_job_id}")
    body = status.json()
    assert body["status"] == "error"
    assert "npx" in body["error"]
    assert body["result"] is None
