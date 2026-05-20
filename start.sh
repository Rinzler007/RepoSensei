#!/bin/bash

set -e

VENV_DIR=".venv"
ENV_FILE=".env"
HOST="127.0.0.1"
PORT="8000"

# ── Colors ──
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
RESET='\033[0m'

log()  { echo -e "${CYAN}[RepoSensei]${RESET} $1"; }
ok()   { echo -e "${GREEN}[RepoSensei]${RESET} $1"; }
warn() { echo -e "${YELLOW}[RepoSensei]${RESET} $1"; }
err()  { echo -e "${RED}[RepoSensei]${RESET} $1"; }

OLLAMA_STARTED=false

cleanup() {
    echo ""
    log "Shutting down..."

    # Kill uvicorn
    if [ -n "$UVICORN_PID" ] && kill -0 "$UVICORN_PID" 2>/dev/null; then
        kill "$UVICORN_PID" 2>/dev/null
        log "Backend stopped."
    fi

    # Only stop Ollama if we started it
    if [ "$OLLAMA_STARTED" = true ]; then
        pkill -f "ollama serve" 2>/dev/null || true
        log "Ollama stopped."
    fi

    ok "All done. Goodbye!"
    exit 0
}

trap cleanup INT TERM

# ── Check .env exists ──
if [ ! -f "$ENV_FILE" ]; then
    err ".env file not found. Copy .env.example to .env and fill in your settings."
    exit 1
fi

# ── Activate virtual environment ──
if [ ! -d "$VENV_DIR" ]; then
    warn "No .venv found. Creating one..."
    python3 -m venv "$VENV_DIR"
    ok "Virtual environment created."
fi

source "$VENV_DIR/bin/activate"

# ── Install dependencies if needed ──
if ! python -c "import fastapi" 2>/dev/null; then
    log "Installing dependencies..."
    pip install -r requirements.txt -q
    ok "Dependencies installed."
fi

# ── Read LLM_PROVIDER from .env ──
LLM_PROVIDER=$(grep -E '^LLM_PROVIDER=' "$ENV_FILE" | cut -d '=' -f2 | tr -d '[:space:]')

# ── Start Ollama if needed ──
if [ "$LLM_PROVIDER" = "ollama" ]; then
    if pgrep -f "ollama serve" > /dev/null 2>&1; then
        ok "Ollama is already running."
    else
        log "Starting Ollama..."
        ollama serve > /tmp/ollama.log 2>&1 &
        OLLAMA_STARTED=true

        # Wait for Ollama to be ready
        for i in $(seq 1 15); do
            if curl -s http://127.0.0.1:11434 > /dev/null 2>&1; then
                ok "Ollama is ready."
                break
            fi
            if [ "$i" -eq 15 ]; then
                err "Ollama failed to start. Check /tmp/ollama.log for details."
                exit 1
            fi
            sleep 1
        done
    fi
fi

# ── Start backend ──
log "Starting RepoSensei backend..."
uvicorn app:app --host "$HOST" --port "$PORT" > /tmp/reposensei.log 2>&1 &
UVICORN_PID=$!

# Wait for backend to be ready
for i in $(seq 1 15); do
    if curl -s "http://$HOST:$PORT/health" > /dev/null 2>&1; then
        ok "Backend is ready."
        break
    fi
    if [ "$i" -eq 15 ]; then
        err "Backend failed to start. Check /tmp/reposensei.log for details."
        cleanup
        exit 1
    fi
    sleep 1
done

# ── Open browser ──
ok "Opening http://$HOST:$PORT in your browser..."
open "http://$HOST:$PORT"

echo ""
echo -e "${GREEN}  RepoSensei is running!${RESET}"
echo -e "  URL:      ${CYAN}http://$HOST:$PORT${RESET}"
echo -e "  Provider: ${CYAN}${LLM_PROVIDER}${RESET}"
echo -e "  Press ${YELLOW}Ctrl+C${RESET} to stop."
echo ""

# ── Keep alive ──
wait $UVICORN_PID
