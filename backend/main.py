import json
import pathlib
import uuid

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile

from script_generator import extract_text, generate_script

app = FastAPI(title="learnflow-ai")

UPLOADS_DIR = pathlib.Path("uploads")

# In-memory job store. Keys are job_id strings.
# Each value: {"status": str, "result": dict | None, "error": str | None}
jobs: dict[str, dict] = {}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")
    contents = await file.read()
    if len(contents) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File exceeds 20 MB limit")
    file_id = str(uuid.uuid4())
    UPLOADS_DIR.mkdir(exist_ok=True)
    (UPLOADS_DIR / f"{file_id}.pdf").write_bytes(contents)
    return {"file_id": file_id}


@app.post("/generate/{file_id}")
def generate(file_id: str, background_tasks: BackgroundTasks) -> dict:
    pdf_path = UPLOADS_DIR / f"{file_id}.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail=f"No uploaded file with id {file_id!r}")
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "pending", "result": None, "error": None}
    background_tasks.add_task(_run_generate, job_id, file_id, pdf_path)
    return {"job_id": job_id}


def _run_generate(job_id: str, file_id: str, pdf_path: pathlib.Path) -> None:
    jobs[job_id]["status"] = "running"
    try:
        text = extract_text(pdf_path)
        script = generate_script(file_id, text)
        script_path = pdf_path.parent / f"{file_id}_script.json"
        script_path.write_text(json.dumps(script))
        jobs[job_id] = {"status": "complete", "result": script, "error": None}
    except Exception as exc:
        jobs[job_id] = {"status": "error", "result": None, "error": str(exc)}


@app.get("/job/{job_id}")
def job_status(job_id: str) -> dict:
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=f"No job with id {job_id!r}")
    job = jobs[job_id]
    return {"job_id": job_id, **job}
