from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import main
from main import app, jobs

client = TestClient(app)

_FAKE_QUIZ = {
    "questions": [
        {
            "question": "What is the sample space?",
            "options": ["A. Set of outcomes", "B. A probability", "C. An event", "D. A function"],
            "answer": "A",
        },
        {
            "question": "What does E[X] represent?",
            "options": ["A. Variance", "B. Expected value", "C. Probability", "D. Standard deviation"],
            "answer": "B",
        },
    ]
}

_COMPLETE_SCRIPT = {
    "file_id": "abc-123",
    "title": "Test Doc",
    "slides": [
        {
            "index": 0,
            "title": "Intro",
            "narration": "This is the introduction.",
            "bullets": ["Point A"],
        }
    ],
}


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    jobs.clear()
    yield
    jobs.clear()


def _seed_complete_job(job_id: str = "gen-job-001") -> str:
    jobs[job_id] = {"status": "complete", "result": _COMPLETE_SCRIPT, "error": None}
    return job_id


# --- 200 success ---

def test_quiz_returns_questions():
    job_id = _seed_complete_job()
    with patch("main.generate_quiz", return_value=_FAKE_QUIZ):
        resp = client.get(f"/quiz/{job_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["job_id"] == job_id
    assert len(body["questions"]) == 2
    assert body["questions"][0]["answer"] == "A"


def test_quiz_passes_script_to_generate_quiz():
    job_id = _seed_complete_job()
    with patch("main.generate_quiz", return_value=_FAKE_QUIZ) as mock_gq:
        client.get(f"/quiz/{job_id}")
    mock_gq.assert_called_once_with(_COMPLETE_SCRIPT)


# --- 404 ---

def test_quiz_unknown_job_id():
    resp = client.get("/quiz/does-not-exist")
    assert resp.status_code == 404


# --- 400 for non-complete jobs ---

@pytest.mark.parametrize("status", ["pending", "running", "error"])
def test_quiz_job_not_complete(status):
    jobs["job-x"] = {"status": status, "result": None, "error": None}
    resp = client.get("/quiz/job-x")
    assert resp.status_code == 400
    assert status in resp.json()["detail"]
