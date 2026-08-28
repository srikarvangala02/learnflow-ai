# Pre-staged for the commented render/upload stubs below — not used by active routes.
import subprocess  # noqa: F401
import uuid  # noqa: F401

from fastapi import BackgroundTasks, FastAPI

app = FastAPI(title="learnflow-ai")

# In-memory job store. Keys are job_id strings; values are status strings.
jobs: dict[str, str] = {}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /upload
# ---------------------------------------------------------------------------
# Accept: UploadFile (PDF)
# Action: Save to backend/uploads/{file_id}.pdf
# Return: {"file_id": str}
#
# from fastapi import UploadFile, File
# import shutil, pathlib
#
# @app.post("/upload")
# async def upload(file: UploadFile = File(...)) -> dict:
#     file_id = str(uuid.uuid4())
#     dest = pathlib.Path("uploads") / f"{file_id}.pdf"
#     dest.parent.mkdir(exist_ok=True)
#     with dest.open("wb") as f:
#         shutil.copyfileobj(file.file, f)
#     return {"file_id": file_id}


# ---------------------------------------------------------------------------
# POST /generate/{file_id}
# ---------------------------------------------------------------------------
# Action: Extract text with pdfplumber, call Claude API to produce a
#         structured script JSON, persist to uploads/{file_id}_script.json.
# Return: {"job_id": str}
#
# @app.post("/generate/{file_id}")
# def generate(file_id: str) -> dict:
#     job_id = str(uuid.uuid4())
#     jobs[job_id] = "pending"
#     # TODO: pdfplumber.open(...) → anthropic.Anthropic().messages.create(...)
#     return {"job_id": job_id}


# ---------------------------------------------------------------------------
# POST /render/{job_id}
# ---------------------------------------------------------------------------
# Action: Enqueue _run_remotion_render as a background task.
# Return: {"job_id": str, "status": "pending"} immediately.
#
# @app.post("/render/{job_id}")
# def render(job_id: str, background_tasks: BackgroundTasks) -> dict:
#     jobs[job_id] = "pending"
#     background_tasks.add_task(_run_remotion_render, job_id)
#     return {"job_id": job_id, "status": "pending"}
#
#
# def _run_remotion_render(job_id: str) -> None:
#     # NOTE: subprocess.run blocks the calling thread. BackgroundTasks runs
#     # sync functions in a thread pool, so this is safe for MVP.
#     jobs[job_id] = "running"
#     result = subprocess.run(
#         [
#             "npx", "remotion", "render",
#             "src/index.ts",          # entry point
#             "LearnFlowSlide",        # composition id
#             f"out/{job_id}.mp4",     # output path (relative to render/)
#         ],
#         cwd="../render",
#         capture_output=True,
#     )
#     jobs[job_id] = "complete" if result.returncode == 0 else "error"


# ---------------------------------------------------------------------------
# GET /job/{job_id}
# ---------------------------------------------------------------------------
# Return: {"job_id": str, "status": "pending|running|complete|error|not_found"}
#
# @app.get("/job/{job_id}")
# def job_status(job_id: str) -> dict:
#     return {"job_id": job_id, "status": jobs.get(job_id, "not_found")}


# ---------------------------------------------------------------------------
# GET /quiz/{job_id}
# ---------------------------------------------------------------------------
# Return: {"job_id": str, "questions": list[dict]}
# Questions shape: [{"question": str, "choices": list[str], "answer_index": int}]
#
# @app.get("/quiz/{job_id}")
# def quiz(job_id: str) -> dict:
#     # TODO: generate 3-5 MCQ questions from the source PDF text via Claude API
#     return {"job_id": job_id, "questions": []}


# ---------------------------------------------------------------------------
# POST /eval
# ---------------------------------------------------------------------------
# Body: {"job_id": str}
# Return: {"narration_score": float, "full_source_score": float, "delta": float}
#
# @app.post("/eval")
# def eval_accuracy(body: dict) -> dict:
#     # TODO: call eval/eval.py compare_accuracy() with both context types
#     return {"narration_score": 0.0, "full_source_score": 0.0, "delta": 0.0}
