# RepoSensei

RepoSensei is an AI-powered codebase mentor that analyzes any public GitHub repository and explains:

- What it does
- How it's structured
- Key modules and their responsibilities
- Critical execution flows
- A Mermaid architecture diagram
- An onboarding path for new developers

Because we have all opened a new repo and thought: **"Where do I even start ?"**

---

## Features

- Paste a GitHub URL: Get a full architecture breakdown
- Structured JSON report or Markdown document
- Module map with key files
- Critical user flows with file references
- Mermaid architecture diagram
- Onboarding path for new devs
- Suggested improvements grounded in the actual code
- Works with any language or stack

---

## Tech

- **FastAPI** (Python backend)
- **Ollama**: local LLM, free, no API key needed (default)
- **Gemini**: Google's API, free tier available
- Git clone + heuristic file selection + signal extraction

---

## Quickstart

### 1. Install Ollama

**MacOS:**

```bash
brew install ollama
```

**Windows:**

```powershell
winget install Ollama.Ollama
```

Or download the installer directly from [ollama.com/download](https://ollama.com/download).

### 2. Pull a model

**16GB RAM (recommended):**

```bash
ollama pull qwen2.5:14b-instruct
```

**8GB RAM:**

```bash
ollama pull qwen2.5:7b-instruct
```

### 3. Configure environment

```bash
cp .env.example .env
```

For Ollama (default), your `.env` should look like:

```
LLM_PROVIDER=ollama
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:14b-instruct
RESPONSE_MODE=strict
```

### 4. Run

```bash
./start.sh
```

That's it. The script will:

- Start Ollama automatically
- Install dependencies if needed
- Start the backend
- Open the browser at `http://127.0.0.1:8000`

Press `Ctrl+C` to stop everything.

---

## Using Gemini (Free Tier)

1. Get a free API key at [aistudio.google.com](https://aistudio.google.com)
2. Update `.env`:

```
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-2.0-flash
```

3. Run as usual:

```bash
./start.sh
```

---

## Response Modes

Set `RESPONSE_MODE` in `.env`:

| Mode               | Behaviour                                                             |
| ------------------ | --------------------------------------------------------------------- |
| `strict` (default) | Never invent routes or features, only states what's evidenced in code |
| `helpful`          | May suggest likely flows, clearly labeled as "Likely"                 |

---

## MCP Server (Claude Code Integration)

RepoSensei can run as an MCP server, letting you analyze repos directly from Claude Code without opening the browser.

### Connect to Claude Code

```bash
claude mcp add reposensei \
  -e LLM_PROVIDER=ollama \
  -e OLLAMA_HOST=http://127.0.0.1:11434 \
  -e OLLAMA_MODEL=qwen2.5:14b-instruct \
  -- /absolute/path/to/.venv/bin/python /absolute/path/to/mcp_server.py
```

### Usage in Claude Code

Once connected, just ask Claude naturally:

```
Analyze https://github.com/user/repo for me
```

Claude will call the `analyze_repository` tool and return the full architecture breakdown inline.

### Tool parameters

| Parameter  | Type                | Description                         |
| ---------- | ------------------- | ----------------------------------- |
| `repo_url` | string              | Public GitHub URL to analyze        |
| `format`   | `markdown` / `json` | Output format (default: `markdown`) |

---

## API Endpoints

| Endpoint   | Method | Description                                               |
| ---------- | ------ | --------------------------------------------------------- |
| `/`        | GET    | Web UI                                                    |
| `/analyze` | POST   | Returns structured JSON report + Markdown doc in one call |
| `/health`  | GET    | Health check                                              |

**Example request:**

```json
{
  "repo_url": "https://github.com/user/repo"
}
```

**Example response:**

```json
{
  "report": {
    "repo_name": "...",
    "overview": "...",
    "tech_stack": [],
    "...": "..."
  },
  "md": "# Architecture - ...\n..."
}
```
