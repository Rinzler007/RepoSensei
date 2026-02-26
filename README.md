# RepoSensei 🥋

RepoSensei is a small AI-powered “codebase mentor” that analyzes any public GitHub repository and explains:

- what it does,
- how it’s structured,
- key modules,
- critical execution flows,
- and a Mermaid architecture diagram.

Because we have all opened a new repo and thought:
**“Where do I even start?”** 😭

## Features

- Repo URL → Architecture Walkthrough (JSON)
- Module map + key files
- 2–3 critical flows
- Mermaid diagram
- Onboarding path for new devs

## Tech

- FastAPI (Python)
- Git clone + heuristic file selection
- Local LLM via **Ollama** (default)
- Optional OpenAI provider (toggle via `.env`)

---

## Setup (Ollama - Recommended)

### 1) Install Ollama

macOS:

```bash
brew install ollama
ollama serve
```

### 2) Pull a model

```bash
ollama pull qwen2.5:7b-instruct
```

# or

```bash
ollama pull llama3.1:8b
```

### 3) Run RepoSensei

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
uvicorn app:app --reload --port 8000
```

### 4) Open docs

- http://127.0.0.1:8000/docs

### 5) Test

- Here I am referring fastapi repository as an example.

```bash
curl -X POST http://127.0.0.1:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"repo_url":"https://github.com/tiangolo/fastapi"}'
```

### 6) Switching to OpenAI (Optional)

- Set in .env

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=YOUR_KEY
OPENAI_MODEL=gpt-4.1-mini
```
