from __future__ import annotations

from pathlib import Path
from collections import Counter
import re

_EXT_LANG = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".jsx": "JavaScript",
    ".go": "Go",
    ".java": "Java",
    ".kt": "Kotlin",
    ".rb": "Ruby",
    ".php": "PHP",
    ".rs": "Rust",
    ".c": "C",
    ".cc": "C++",
    ".cpp": "C++",
    ".h": "C/C++",
    ".hpp": "C++",
    ".cs": "C#",
}

_IGNORE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".cache",
    ".pytest_cache",
    ".mypy_cache",
}

_ENTRYPOINT_FILES_NEAR_ROOT = {
    "manage.py",
    "pyproject.toml",
    "requirements.txt",
    "setup.py",
    "Pipfile",
    "poetry.lock",
    "environment.yml",
    "Dockerfile",
    "docker-compose.yml",
    "compose.yml",
    "Makefile",
    "package.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "package-lock.json",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "README.md",
    "README.rst",
    "README.txt",
}

_ENTRYPOINT_FILES_ANYWHERE = {
    # python
    "app.py", "main.py", "server.py", "wsgi.py", "asgi.py", "manage.py",
    # node
    "index.js", "index.ts", "app.js", "app.ts", "server.js", "server.ts",
    # go/java
    "main.go", "Main.java", "main.java",
}

_ROUTE_RE = re.compile(r'(["\'])(/[^"\']+)\1')


def _iter_files(root: Path):
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if set(p.parts) & _IGNORE_DIRS:
            continue
        yield p


def build_signals(root: Path) -> dict:
    root = Path(root)

    # --------- languages ----------
    lang_counts: Counter[str] = Counter()
    for p in _iter_files(root):
        lang = _EXT_LANG.get(p.suffix.lower())
        if lang:
            lang_counts[lang] += 1

    language_rank = [k for k, _ in lang_counts.most_common()]
    languages = list(language_rank)
    primary_language = language_rank[0] if language_rank else None

    # --------- entrypoints near root ----------
    entrypoints_near_root: list[str] = []
    for p in _iter_files(root):
        rel = p.relative_to(root).as_posix()
        if rel.count("/") <= 1 and p.name in _ENTRYPOINT_FILES_NEAR_ROOT:
            entrypoints_near_root.append(rel)

    # dedupe preserve order
    seen = set()
    ep_root: list[str] = []
    for e in entrypoints_near_root:
        if e not in seen:
            seen.add(e)
            ep_root.append(e)

    # --------- entrypoints anywhere (high-signal filenames) ----------
    entrypoints_anywhere: list[str] = []
    for p in _iter_files(root):
        if p.name in _ENTRYPOINT_FILES_ANYWHERE:
            entrypoints_anywhere.append(p.relative_to(root).as_posix())

    seen2 = set()
    ep_any: list[str] = []
    for e in entrypoints_anywhere:
        if e not in seen2:
            seen2.add(e)
            ep_any.append(e)

    # --------- monorepo hint ----------
    # If we see multiple manifests in different dirs, that’s a hint (not a conclusion).
    manifest_names = {"package.json", "pyproject.toml", "go.mod", "pom.xml", "build.gradle", "build.gradle.kts"}
    manifest_paths = []
    for p in _iter_files(root):
        if p.name in manifest_names:
            manifest_paths.append(p.relative_to(root).as_posix())
    monorepo_hint = len({Path(x).parent.as_posix() for x in manifest_paths}) >= 2

    # --------- routes_sample (lightweight) ----------
    routes_sample: list[str] = []
    candidates: list[Path] = []

    # prefer scanning entrypoint-ish code files
    for rel in ep_root + ep_any:
        if rel.endswith((".py", ".js", ".ts")):
            fp = root / rel
            if fp.exists() and fp.is_file():
                candidates.append(fp)

    # fallback if none
    for fallback in ["app.py", "main.py", "server.py", "index.js", "src/index.js"]:
        fp = root / fallback
        if fp.exists() and fp.is_file():
            candidates.append(fp)

    for fp in candidates[:6]:
        try:
            txt = fp.read_text(errors="ignore")
        except Exception:
            continue
        for m in _ROUTE_RE.finditer(txt):
            route = m.group(2)
            if route.startswith("/") and len(route) <= 60:
                routes_sample.append(route)

    rs_seen = set()
    routes_sample2: list[str] = []
    for r in routes_sample:
        if r not in rs_seen:
            rs_seen.add(r)
            routes_sample2.append(r)

    return {
        "languages": languages,
        "language_rank": language_rank,
        "language_counts": dict(lang_counts),
        "primary_language": primary_language,
        "entrypoints_near_root": ep_root,
        "entrypoints_anywhere": ep_any,
        "entrypoints": ep_root,  # keep old key for compatibility with your analyzer/render
        "monorepo_hint": monorepo_hint,
        "manifest_paths": manifest_paths[:30],
        "routes_sample": routes_sample2[:20],
        "framework_hints": [],          # intentionally empty (no hardcoding)
        "capability_evidence": {},      # keep for later expansion
    }