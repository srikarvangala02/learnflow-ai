from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import main
from main import app, jobs

client = TestClient(app)

_SCRIPT = {
    "file_id": "abc-123",
    "title": "Test Doc",
    "slides": [{"index": 0, "title": "Intro", "narration": "This is the introduction.", "bullets": ["Point A"]}],
}

_QUESTIONS = [
    {
        "question": "What is the sample space?",
        "options": ["A. Set of outcomes", "B. A probability", "C. An event", "D. A function"],
        "answer": "A",
        "topic": "Sample Space",
    },
    {
        "question": "What does E[X] represent?",
        "options": ["A. Variance", "B. Expected value", "C. Probability", "D. Std dev"],
        "answer": "B",
        "topic": "Expected Value",
    },
]

_FAKE_EVAL_RESULT = {
    "narration_score": 1,
    "full_source_score": 2,
    "total_questions": 2,
    "questions": [
        {
            "question": _QUESTIONS[0]["question"],
            "correct_answer": "A",
            "narration_answer": "B",
            "narration_correct": False,
            "full_source_answer": "A",
            "full_source_correct": True,
        },
        {
            "question": _QUESTIONS[1]["question"],
            "correct_answer": "B",
            "narration_answer": "B",
            "narration_correct": True,
            "full_source_answer": "B",
            "full_source_correct": True,
        },
    ],
}

_FAKE_EVAL_RESULT_WITH_FOCUS = {
    **_FAKE_EVAL_RESULT,
    "focus_areas": [
        {"topic": "Sample Space", "explanation": "Review the definition of a sample space."}
    ],
}


@pytest.fixture(autouse=True)
def reset_state(tmp_path, monkeypatch):
    jobs.clear()
    monkeypatch.setattr(main, "UPLOADS_DIR", tmp_path)
    # Write a minimal fake PDF placeholder so extract_text is patchable
    (tmp_path / "abc-123.pdf").write_bytes(b"%PDF-1.4 fake")
    yield
    jobs.clear()


def _seed_complete_job(job_id: str = "gen-job-001") -> str:
    jobs[job_id] = {"status": "complete", "result": _SCRIPT, "error": None}
    return job_id


# --- 200 success ---

def test_eval_returns_scores():
    job_id = _seed_complete_job()
    with patch("main.evaluate_quiz", return_value=_FAKE_EVAL_RESULT), \
         patch("main.extract_text", return_value="full pdf text"):
        resp = client.post("/eval", json={"job_id": job_id, "questions": _QUESTIONS})
    assert resp.status_code == 200
    body = resp.json()
    assert body["job_id"] == job_id
    assert body["narration_score"] == 1
    assert body["full_source_score"] == 2
    assert body["total_questions"] == 2


def test_eval_passes_correct_args():
    job_id = _seed_complete_job()
    with patch("main.evaluate_quiz", return_value=_FAKE_EVAL_RESULT) as mock_eval, \
         patch("main.extract_text", return_value="full pdf text"):
        client.post("/eval", json={"job_id": job_id, "questions": _QUESTIONS})
    mock_eval.assert_called_once_with(_SCRIPT, "full pdf text", _QUESTIONS, None)


def test_eval_with_user_answers_returns_focus_areas():
    job_id = _seed_complete_job()
    with patch("main.evaluate_quiz", return_value=_FAKE_EVAL_RESULT_WITH_FOCUS), \
         patch("main.extract_text", return_value="full pdf text"):
        resp = client.post("/eval", json={
            "job_id": job_id,
            "questions": _QUESTIONS,
            "user_answers": ["B", "B"],  # first answer wrong (correct is A)
        })
    assert resp.status_code == 200
    body = resp.json()
    assert "focus_areas" in body
    assert len(body["focus_areas"]) == 1
    assert body["focus_areas"][0]["topic"] == "Sample Space"


def test_eval_passes_user_answers_to_evaluate_quiz():
    job_id = _seed_complete_job()
    with patch("main.evaluate_quiz", return_value=_FAKE_EVAL_RESULT_WITH_FOCUS) as mock_eval, \
         patch("main.extract_text", return_value="full pdf text"):
        client.post("/eval", json={
            "job_id": job_id,
            "questions": _QUESTIONS,
            "user_answers": ["B", "B"],
        })
    args, _ = mock_eval.call_args
    assert args[3] == ["B", "B"]


def test_eval_without_user_answers_omits_focus_areas():
    job_id = _seed_complete_job()
    with patch("main.evaluate_quiz", return_value=_FAKE_EVAL_RESULT), \
         patch("main.extract_text", return_value="full pdf text"):
        resp = client.post("/eval", json={"job_id": job_id, "questions": _QUESTIONS})
    assert resp.status_code == 200
    body = resp.json()
    assert "focus_areas" not in body


# --- 404 ---

def test_eval_unknown_job_id():
    resp = client.post("/eval", json={"job_id": "does-not-exist", "questions": _QUESTIONS})
    assert resp.status_code == 404


# --- 400 for non-complete jobs ---

@pytest.mark.parametrize("status", ["pending", "running", "error"])
def test_eval_job_not_complete(status):
    jobs["job-x"] = {"status": status, "result": None, "error": None}
    resp = client.post("/eval", json={"job_id": "job-x", "questions": _QUESTIONS})
    assert resp.status_code == 400
    assert status in resp.json()["detail"]
