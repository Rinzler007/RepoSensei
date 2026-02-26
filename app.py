from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, HttpUrl

from reposensei.analyzer.analyze import analyze_repo
from reposensei.render import to_architecture_md
from reposensei.schemas import RepoReport

app = FastAPI(title="RepoSensei 🥋", version="1.0.0")


class AnalyzeRequest(BaseModel):
    repo_url: HttpUrl
    model: str | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze", response_model=RepoReport)
def analyze(req: AnalyzeRequest):
    try:
        # keep JSON endpoint simple
        return analyze_repo(str(req.repo_url), model_override=req.model)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/architecture-md", response_class=PlainTextResponse)
def architecture_md(req: AnalyzeRequest):
    try:
        # IMPORTANT: get signals too for evidence-gated markdown + transparency section
        report, signals = analyze_repo(str(req.repo_url), model_override=req.model, return_signals=True)
        return to_architecture_md(report, signals=signals)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))