from __future__ import annotations

from pathlib import Path
from collections import Counter, defaultdict
import re

IGNORE_DIRS = {
    ".git", "node_modules", "dist", "build", "target", "vendor",
    ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".next", ".turbo", ".parcel-cache", ".cache"
}

PRIORITY_FILES = {
    # docs
    "README.md", "README.rst", "README.txt",
    # python
    "pyproject.toml", "requirements.txt", "Pipfile", "poetry.lock", "setup.py",
    # node
    "package.json", "pnpm-lock.yaml", "yarn.lock", "package-lock.json",
    # go
    "go.mod", "go.sum",
    # java
    "pom.xml", "build.gradle", "build.gradle.kts",
    # infra
    "Dockerfile", "docker-compose.yml", "Makefile",
    "terraform.tf", "main.tf",
    "serverless.yml", "template.yaml",
}

# Directories that tend to contain real code (generic)
CODE_DIR_HINTS = {"src", "app", "apps", "api", "server", "backend", "frontend", "cmd", "pkg", "internal", "lib"}

# Directories that are often heavy/non-core
DEPRIORITIZE_DIRS = {"docs", "doc", "documentation", "site", "website", "examples", "example", "demo", "demos", "public"}

# Entry-ish filenames across languages
ENTRY_FILENAMES = {
    "main.py", "app.py", "server.py", "wsgi.py", "asgi.py",
    "index.js", "index.ts", "server.js", "server.ts", "app.js", "app.ts",
    "main.go",
    "main.java",
}

# --- regexes for lightweight import scanning (generic, not framework-specific) ---
PY_IMPORT_RE = re.compile(r"^\s*(?:from\s+([a-zA-Z0-9_\.]+)\s+import|import\s+([a-zA-Z0-9_\.]+))", re.M)
JS_IMPORT_RE = re.compile(r"^\s*import\s+.*?from\s+['\"](.+?)['\"]\s*;?\s*$", re.M)
JS_REQUIRE_RE = re.compile(r"require\(\s*['\"](.+?)['\"]\s*\)")
GO_IMPORT_RE = re.compile(r'^\s*import\s*(?:\(\s*)?["\']([^"\']+)["\']', re.M)


def iter_repo_files(root: Path):
    for p in root.rglob("*"):
        if any(part in IGNORE_DIRS for part in p.parts):
            continue
        if p.is_file():
            yield p


def build_tree(root: Path, max_entries: int = 600) -> str:
    lines = []
    count = 0
    for p in sorted(iter_repo_files(root), key=lambda x: str(x)):
        rel = p.relative_to(root)
        lines.append(str(rel))
        count += 1
        if count >= max_entries:
            lines.append("... (truncated)")
            break
    return "\n".join(lines)


def _safe_read_text(p: Path, max_chars: int = 120_000) -> str:
    try:
        return p.read_text(errors="ignore")[:max_chars]
    except Exception:
        return ""


def _build_basename_index(root: Path) -> dict[str, list[Path]]:
    """
    Map "foo" -> [foo.py, foo.js, foo.ts, ...] for repo-local matching.
    """
    idx: dict[str, list[Path]] = defaultdict(list)
    for p in iter_repo_files(root):
        stem = p.stem.lower()
        idx[stem].append(p)
    return idx


def _collect_import_centrality(root: Path, max_files_to_scan: int = 250) -> tuple[Counter[str], Counter[str]]:
    """
    Returns:
      - inbound_refs: Counter[file_rel] = how many times this file is referenced by others
      - outbound_refs: Counter[file_rel] = how many imports this file makes (proxy for being an entry/wiring file)

    This is intentionally lightweight and generic:
    - Python: import/from
    - JS/TS: import/require
    - Go: import "..."
    We only resolve "local-ish" imports (./, ../, or module basenames).
    """
    basename_idx = _build_basename_index(root)

    inbound_refs: Counter[str] = Counter()
    outbound_refs: Counter[str] = Counter()

    # Prefer scanning code-ish files only
    code_suffixes = {".py", ".js", ".ts", ".tsx", ".jsx", ".go"}
    candidates = []
    for p in iter_repo_files(root):
        if p.suffix.lower() in code_suffixes:
            candidates.append(p)

    # scan up to N files (largest first gives more signal)
    candidates.sort(key=lambda p: p.stat().st_size if p.exists() else 0, reverse=True)
    candidates = candidates[:max_files_to_scan]

    def relposix(p: Path) -> str:
        return p.relative_to(root).as_posix()

    for src in candidates:
        text = _safe_read_text(src, max_chars=80_000)
        if not text:
            continue

        src_rel = relposix(src)

        refs: set[str] = set()

        suf = src.suffix.lower()

        if suf == ".py":
            for m in PY_IMPORT_RE.finditer(text):
                mod = (m.group(1) or m.group(2) or "").strip()
                if not mod:
                    continue
                base = mod.split(".")[-1].lower()
                # match by basename index
                for tgt in basename_idx.get(base, []):
                    refs.add(relposix(tgt))

        elif suf in {".js", ".ts", ".tsx", ".jsx"}:
            for m in JS_IMPORT_RE.finditer(text):
                path = m.group(1).strip()
                if path.startswith("."):
                    # local relative: ./foo or ../bar
                    base = Path(path).name.split(".")[0].lower()
                    for tgt in basename_idx.get(base, []):
                        refs.add(relposix(tgt))
                else:
                    # module import: try basename match (repo-local)
                    base = path.split("/")[-1].split(".")[0].lower()
                    for tgt in basename_idx.get(base, []):
                        refs.add(relposix(tgt))

            for m in JS_REQUIRE_RE.finditer(text):
                path = m.group(1).strip()
                base = Path(path).name.split(".")[0].lower()
                for tgt in basename_idx.get(base, []):
                    refs.add(relposix(tgt))

        elif suf == ".go":
            # Go imports are module paths; basename match still works reasonably
            for m in GO_IMPORT_RE.finditer(text):
                imp = m.group(1).strip()
                base = imp.split("/")[-1].split(".")[0].lower()
                for tgt in basename_idx.get(base, []):
                    refs.add(relposix(tgt))

        # Update counters
        if refs:
            outbound_refs[src_rel] += len(refs)
            for tgt_rel in refs:
                if tgt_rel != src_rel:
                    inbound_refs[tgt_rel] += 1

    return inbound_refs, outbound_refs


def pick_important_files(root: Path, max_files: int = 40) -> list[Path]:
    """
    Generic, repo-agnostic file picker.
    Key idea:
      1) Always include manifests/README near root
      2) Include likely entry files
      3) Include "central" files (imported by many others)
      4) Add scored fallbacks based on directory/file heuristics
    """
    # 1) Always include priority files near root (depth <= 1)
    pinned: list[Path] = []
    for p in iter_repo_files(root):
        rel = p.relative_to(root).as_posix()
        if rel.count("/") <= 1 and p.name in PRIORITY_FILES:
            pinned.append(p)

    # ensure README first if present
    for rn in ["README.md", "README.rst", "README.txt"]:
        rp = root / rn
        if rp.exists() and rp not in pinned:
            pinned.insert(0, rp)

    # 2) Likely entry files (anywhere)
    entry: list[Path] = []
    for p in iter_repo_files(root):
        if p.name.lower() in ENTRY_FILENAMES:
            entry.append(p)

    # 3) Import centrality scoring (generic + powerful)
    inbound, outbound = _collect_import_centrality(root)
    central: list[tuple[int, Path]] = []
    for rel, score in inbound.most_common(80):
        fp = root / rel
        if fp.exists() and fp.is_file():
            central.append((score, fp))

    # 4) Heuristic scoring fallback (your original logic, lightly improved)
    candidates: list[tuple[int, Path]] = []
    for p in iter_repo_files(root):
        rel = p.relative_to(root)
        rel_str = str(rel).lower()
        name = p.name

        score = 0
        if name in PRIORITY_FILES:
            score += 120

        parts = set(rel.parts)
        if parts & CODE_DIR_HINTS:
            score += 40
        if parts & DEPRIORITIZE_DIRS:
            score -= 35

        lowname = name.lower()
        if lowname in ENTRY_FILENAMES:
            score += 90

        if lowname.endswith(("routes.py", "router.py", "handlers.go", "controller.ts", "controller.js", "urls.py")):
            score += 45
        if any(x in rel_str for x in ["route", "router", "controller", "handler", "endpoint", "service"]):
            score += 20
        if any(x in rel_str for x in ["config", "settings", "infra", "deploy", ".github"]):
            score += 15

        try:
            size = p.stat().st_size
        except OSError:
            continue

        # skip huge files
        if size > 350_000:
            continue

        # prefer smaller files a bit
        score -= int(size / 12_000)

        # boost files that are "wiring" (import many)
        relposix = p.relative_to(root).as_posix()
        if outbound.get(relposix, 0) >= 8:
            score += 25

        if score > 0:
            candidates.append((score, p))

    candidates.sort(key=lambda x: x[0], reverse=True)

    # Merge everything with de-dupe, preserve order of importance
    def add_unique(out: list[Path], items: list[Path]):
        seen = {x.resolve() for x in out}
        for it in items:
            try:
                rp = it.resolve()
            except Exception:
                rp = it
            if rp not in seen:
                out.append(it)
                seen.add(rp)

    picked: list[Path] = []
    add_unique(picked, pinned)
    add_unique(picked, entry)

    # add central files (most imported)
    add_unique(picked, [p for _, p in central])

    # add heuristic candidates
    add_unique(picked, [p for _, p in candidates])

    return picked[:max_files]


def read_files(root: Path, files: list[Path], max_total_chars: int = 180_000) -> str:
    """
    Reads files and returns a stitched context string with per-file caps and total cap.
    """
    chunks = []
    total = 0

    for p in files:
        rel = p.relative_to(root)
        try:
            text = p.read_text(errors="ignore")
        except Exception:
            continue

        # per-file cap
        snippet = text[:28_000]

        block = f"\n\n===== FILE: {rel} =====\n{snippet}"
        if total + len(block) > max_total_chars:
            chunks.append("\n\n... (content truncated to fit context budget)")
            break

        chunks.append(block)
        total += len(block)

    return "".join(chunks)