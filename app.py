from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl

from backend.analyzer.analyze import analyze_repo
from backend.render import to_architecture_md
from backend.schemas import RepoReport

app = FastAPI(title="RepoSensei 🥋", version="1.0.0")
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse("frontend/index.html")


class AnalyzeRequest(BaseModel):
    repo_url: HttpUrl
    model: str | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


class BothResponse(BaseModel):
    report: RepoReport
    md: str


@app.post("/analyze", response_model=BothResponse)
def analyze_both(req: AnalyzeRequest):
    """Single endpoint that returns both structured JSON and markdown from one LLM call."""
    try:
        report, signals = analyze_repo(str(req.repo_url), model_override=req.model, return_signals=True)
        return BothResponse(report=report, md=to_architecture_md(report, signals=signals))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
