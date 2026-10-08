from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from . import db, outreach, service
from .matching.resume import read_text

app = FastAPI(title="recruited")
STATIC = Path(__file__).resolve().parent.parent / "static"
MAX_UPLOAD = 5 * 1024 * 1024


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/signals")
def signals(type: str | None = None, limit: int = 50):
    with db.session() as conn:
        return service.recent_signals(conn, min(limit, 200), type)


@app.post("/api/outreach")
def outreach_one(job_id: int = Form(...), resume_text: str = Form(...), founder: str = Form(""),
                 sender: str = Form(...), contact: str = Form(""), use_llm: bool = Form(False)):
    """Draft outreach for exactly one job the user picked. There is deliberately no bulk endpoint."""
    if len(resume_text.strip()) < 50:
        raise HTTPException(400, "Resume text is required")
    with db.session() as conn:
        row = conn.execute("SELECT j.*, c.name AS company FROM jobs j JOIN companies c ON c.id=j.company_id "
                           "WHERE j.id=?", (job_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Job not found")
        job = dict(row)
        signals = [dict(r) for r in conn.execute(
            "SELECT * FROM signals WHERE company_id=? ORDER BY published_at DESC", (job["company_id"],))]
    out = outreach.draft(job, signals, resume_text, founder, sender, contact)
    out["prompt"] = outreach.build_prompt(job, signals, resume_text, founder)
    if use_llm:
        out["llm_email"] = outreach.ollama_refine(out["prompt"])
    return out


@app.post("/api/match")
async def match(resume: UploadFile | None = File(None), text: str = Form(""),
                location: str = Form(""), remote_only: bool = Form(False)):
    content = text
    if resume is not None:
        data = await resume.read()
        if len(data) > MAX_UPLOAD:
            raise HTTPException(413, "Resume too large (5MB max)")
        content = read_text(data, resume.filename or "")
    if len(content.strip()) < 50:
        raise HTTPException(400, "Provide a resume file or at least a few lines of text")
    # Resume text is processed in memory only and never stored.
    with db.session() as conn:
        out = service.match_resume(conn, content, location=location, remote_only=remote_only)
    out["resume_text"] = content  # returned to the browser only so outreach can reuse it; not stored
    return out
