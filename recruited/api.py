from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from . import db, service
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
        return service.match_resume(conn, content, location=location, remote_only=remote_only)
