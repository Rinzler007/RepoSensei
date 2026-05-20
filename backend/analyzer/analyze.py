import json
import os
import re
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from git import Repo

from backend.llm import LLMProvider, OllamaProvider, GeminiProvider
from backend.schemas import RepoReport
from backend.signals import build_signals
from backend.utils import build_tree, pick_important_files, read_files

load_dotenv()

# Detect /route-like tokens inside step strings
_ROUTE_LIKE = re.compile(r"(^|\s)(/[^\s]+)")


def _sanitize_report_dict(data: dict, signals: dict, mode: str) -> dict:
    """
    Strict-mode safety net:
    - Remove tech_stack entries that aren't supported by signals.
    - Scrub hallucinated routes/endpoints in critical flow steps.
    - Keep suggested improvements repo-local.
    IMPORTANT: Never mutate file paths/templates (e.g., templates/player/signup_form.html).
    """
    if mode != "strict":
        return data

    # --- Tech stack sanitization ---
    langs_lower = {lang.lower() for lang in signals.get("languages", [])}
    deps_lower = set(signals.get("dependencies", []))  # already lowercased by extractor
    # Always allow core web/data techs by name fragment
    always_allowed = {
        "html", "css", "sql", "json", "yaml", "xml", "graphql", "rest", "grpc", "websocket",
        # Mobile frameworks
        "flutter", "firebase", "react native", "expo",
        # Common frameworks (not always in deps by exact name)
        "django", "flask", "fastapi", "rails", "laravel", "spring", "express",
        "nextjs", "nuxt", "svelte", "angular", "vue", "react",
        "android", "ios", "swiftui", "jetpack",
    }

    tech_stack = data.get("tech_stack", [])
    if isinstance(tech_stack, list):
        cleaned: list[str] = []
        for t in tech_stack:
            if not isinstance(t, str):
                continue
            ts = t.strip()
            ts_low = ts.lower()

            # Allow if it matches a detected language
            if ts_low in langs_lower:
                cleaned.append(ts)
                continue

            # Allow if name fragment matches always_allowed
            if any(a in ts_low for a in always_allowed):
                cleaned.append(ts)
                continue

            # Allow if any dep name is a substring of ts or vice versa (fuzzy)
            if any(dep in ts_low or ts_low in dep for dep in deps_lower):
                cleaned.append(ts)
                continue

            # No evidence at all — strip it
            # (Only happens when LLM hallucinates something with zero grounding)

        seen: set[str] = set()
        out: list[str] = []
        for x in cleaned:
            if x not in seen:
                seen.add(x)
                out.append(x)
        data["tech_stack"] = out

    # --- Route / endpoint sanitization ---
    allowed_routes = set(signals.get("routes_sample", []))

    def scrub_step(step: str) -> str:
        def repl_route(m: re.Match) -> str:
            route = m.group(2)
            if route in allowed_routes:
                return m.group(0)
            return m.group(1) + "(route not confirmed in code)"

        return _ROUTE_LIKE.sub(repl_route, step)

    flows = data.get("critical_flows", [])
    if isinstance(flows, list):
        for f in flows:
            if not isinstance(f, dict):
                continue
            steps = f.get("steps", [])
            if isinstance(steps, list):
                f["steps"] = [scrub_step(s) if isinstance(s, str) else s for s in steps]

    # --- Improvements sanitization ---
    caps = signals.get("capability_evidence", {}) or {}
    has_payments = bool(caps.get("payments"))
    has_email = bool(caps.get("email"))

    imps = data.get("improvements", [])
    if isinstance(imps, list):
        cleaned_imps: list[str] = []
        for s in imps:
            if not isinstance(s, str):
                continue
            low = s.lower()

            if ("payment" in low or "stripe" in low or "paypal" in low) and not has_payments:
                cleaned_imps.append("Keep improvements repo-local; avoid adding major new features not present in code.")
                continue
            if ("email" in low or "smtp" in low) and not has_email:
                cleaned_imps.append("Keep improvements repo-local; avoid claiming integrations not present in code.")
                continue

            cleaned_imps.append(s)

        seen = set()
        out_imps: list[str] = []
        for x in cleaned_imps:
            if x not in seen:
                seen.add(x)
                out_imps.append(x)
        data["improvements"] = out_imps

    return data


def _extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Model did not return JSON.")
    return json.loads(text[start : end + 1])


def _get_provider(model_override: str | None = None) -> tuple[LLMProvider, str]:
    provider_name = (os.getenv("LLM_PROVIDER") or "ollama").strip().lower()

    if provider_name == "gemini":
        api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
        if not api_key:
            raise RuntimeError("LLM_PROVIDER=gemini but GEMINI_API_KEY is not set.")
        model = model_override or (os.getenv("GEMINI_MODEL") or "gemini-2.0-flash")
        return GeminiProvider(api_key=api_key, model=model), model

    host = os.getenv("OLLAMA_HOST") or "http://127.0.0.1:11434"
    model = model_override or (os.getenv("OLLAMA_MODEL") or "qwen2.5:7b-instruct")
    return OllamaProvider(host=host, model=model), model


def _system_instructions(mode: str) -> str:
    base = """You are RepoSensei 🥋 — a staff-level software engineer who onboards developers onto unfamiliar repositories.

Hard rules:
- Do NOT invent routes, commands, features, or integrations.
- Use ONLY the provided REPO SIGNALS and file evidence.
- If something is uncertain, say "Not confirmed in code" and point to likely files to verify.
- Prefer describing behavior/flows as actions; you may cite files in parentheses.
- Suggested improvements must be small, repo-local, and evidence-based. Do not propose unrelated new product features.

Output format:
- Return ONLY valid JSON. No markdown or prose outside JSON.
"""
    if mode == "helpful":
        base += """
Helpful mode:
- You may suggest likely flows or setup steps ONLY if clearly labeled as "Likely" and still grounded in typical conventions.
- Never present a guess as fact.
"""
    return base


JSON_CONTRACT = """Return a JSON object with EXACT keys:
{
  "repo_name": string,
  "tech_stack": [string],
  "overview": string,
  "module_map": [
    {"name": string, "purpose": string, "key_files": [string]}
  ],
  "critical_flows": [
    {"name": string, "steps": [string]}
  ],
  "mermaid_diagram": string,
  "onboarding_path": [string],
  "improvements": [string]
}

Constraints:
- All keys must be present. Use empty arrays if needed.
- For each critical flow step, include the most relevant implementing file in parentheses, e.g. "(player/views.py)".
- Only mention page names/routes if supported by routes_sample or clearly present in snippets; otherwise write "Not confirmed in code" and cite likely files.
- critical_flows.steps must be action-oriented sentences. Avoid raw file paths as steps.
- Only mention concrete routes if they appear in routes_sample or code snippets.
- Only mention capabilities (email/auth/payments/etc.) if capability_evidence supports it; otherwise mark "Not confirmed in code".
- Return ONLY JSON.
"""


def analyze_repo(
    repo_url: str,
    model_override: str | None = None,
    return_signals: bool = False,
):
    llm, model_used = _get_provider(model_override)
    mode = (os.getenv("RESPONSE_MODE") or "strict").strip().lower()

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        Repo.clone_from(repo_url, root, depth=1)

        signals = build_signals(root)
        tree = build_tree(root)
        important = pick_important_files(root)
        file_text = read_files(root, important)

        prompt = (
            f"Repo URL: {repo_url}\n"
            f"Model: {model_used}\n\n"
            "REPO SIGNALS (ground truth hints):\n"
            f"{json.dumps(signals, indent=2)}\n\n"
            "FILE TREE:\n"
            f"{tree}\n\n"
            "IMPORTANT FILE CONTENTS (snippets):\n"
            f"{file_text}\n\n"
            + JSON_CONTRACT
        )

        raw = llm.generate(system=_system_instructions(mode), user=prompt)
        data = _extract_json(raw)

        data = _sanitize_report_dict(data, signals, mode)

        report = RepoReport.model_validate(data)
        if return_signals:
            return report, signals
        return report