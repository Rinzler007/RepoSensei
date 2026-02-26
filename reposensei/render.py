from __future__ import annotations

from reposensei.schemas import RepoReport


def to_architecture_md(r: RepoReport, signals: dict | None = None) -> str:
    lines: list[str] = []
    lines.append(f"# Architecture — {r.repo_name}\n")

    # ---------------- Overview ----------------
    lines.append("## Overview\n")
    overview = (r.overview or "").strip()
    if overview:
        lines.append(overview + "\n")
    else:
        lines.append("Not enough evidence in scanned files to summarize the repository’s purpose.\n")

    # ---------------- Tech Stack ----------------
    lines.append("## Tech Stack\n")
    if r.tech_stack:
        for t in r.tech_stack:
            lines.append(f"- {t}")
    else:
        lines.append("- Not confirmed in code")
    lines.append("")

    # ---------------- Module Map ----------------
    lines.append("## Module Map\n")
    if r.module_map:
        for m in r.module_map:
            lines.append(f"### {m.name}")
            if (m.purpose or "").strip():
                lines.append((m.purpose or "").strip())
            else:
                lines.append("Purpose not confirmed in scanned files.")
            if m.key_files:
                lines.append("\n**Key files:**")
                for f in m.key_files:
                    lines.append(f"- `{f}`")
            lines.append("")
    else:
        lines.append("No modules could be confidently identified from scanned files.\n")

    # ---------------- Critical Flows ----------------
    lines.append("## Critical Flows\n")
    if r.critical_flows:
        for f in r.critical_flows:
            lines.append(f"### {f.name}")
            if f.steps:
                for i, step in enumerate(f.steps, 1):
                    lines.append(f"{i}. {step}")
            else:
                lines.append("No steps confirmed in code.")
            lines.append("")
    else:
        lines.append("No execution flows could be confidently derived from scanned files.\n")

    # ---------------- Diagram ----------------
    lines.append("## Diagram\n")
    mermaid = (r.mermaid_diagram or "").strip()
    if mermaid:
        lines.append("```mermaid")
        lines.append(mermaid)
        lines.append("```")
        lines.append("")
    else:
        lines.append("Diagram not available (insufficient evidence).\n")

    # ---------------- Onboarding Path ----------------
    lines.append("## Onboarding Path\n")
    if r.onboarding_path:
        for i, s in enumerate(r.onboarding_path, 1):
            lines.append(f"{i}. {s}")
    else:
        lines.append("1. Start with README (if present)\n2. Open the entrypoints/manifests (if present)\n3. Follow imports from core modules")
    lines.append("")

    # ---------------- Quickstart (evidence-gated) ----------------
    lines.append("## Quickstart\n")
    if signals:
        eps = signals.get("entrypoints_near_root") or signals.get("entrypoints") or []
        if any(e.endswith("manage.py") for e in eps):
            lines.append("This repo contains `manage.py` (Django-style). Quickstart is likely:\n")
            lines.append("```bash")
            lines.append("python -m venv .venv")
            lines.append("source .venv/bin/activate")
            lines.append("pip install -r requirements.txt  # or pyproject.toml")
            lines.append("python manage.py migrate")
            lines.append("python manage.py runserver")
            lines.append("```")
        elif any(e.endswith("package.json") for e in eps):
            lines.append("This repo contains `package.json`. Quickstart is likely:\n")
            lines.append("```bash")
            lines.append("npm install")
            lines.append("npm run dev  # or npm start (check package.json scripts)")
            lines.append("```")
        elif any(e.endswith(("pyproject.toml", "requirements.txt")) for e in eps):
            lines.append("This repo appears Python-based (pyproject/requirements present). Quickstart is likely:\n")
            lines.append("```bash")
            lines.append("python -m venv .venv")
            lines.append("source .venv/bin/activate")
            lines.append("pip install -r requirements.txt  # or install via pyproject.toml")
            lines.append("```")
        else:
            lines.append("Check the repo README for exact setup/run instructions.\n")
    else:
        lines.append("Check the repo README for exact setup/run instructions.\n")

    lines.append("")

    # ---------------- Improvements ----------------
    lines.append("## Suggested Improvements\n")
    if r.improvements:
        for imp in r.improvements:
            lines.append(f"- {imp}")
    else:
        lines.append("- Not provided")
    lines.append("")

    # ---------------- Evidence (debug-friendly, awesome for LinkedIn demo) ----------------
    if signals:
        lines.append("## Evidence Used (for transparency)\n")
        lines.append("**Languages detected:** " + ", ".join(signals.get("languages", []) or ["None"]) + "\n")

        eps = signals.get("entrypoints_near_root") or signals.get("entrypoints") or []
        if eps:
            lines.append("**Entrypoints/manifests found near root:**")
            for e in eps[:12]:
                lines.append(f"- `{e}`")
            lines.append("")
        else:
            lines.append("**Entrypoints/manifests found near root:** None\n")

        rs = signals.get("routes_sample") or []
        if rs:
            lines.append("**Route-like strings found (sample):**")
            for r0 in rs[:10]:
                lines.append(f"- `{r0}`")
            lines.append("")
        else:
            lines.append("**Route-like strings found:** None\n")

    return "\n".join(lines)