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
    ".dart": "Dart",
    ".swift": "Swift",
    ".m": "Objective-C",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".scala": "Scala",
    ".clj": "Clojure",
    ".hs": "Haskell",
    ".lua": "Lua",
    ".r": "R",
    ".R": "R",
    ".jl": "Julia",
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
    # Flutter / mobile
    ".dart_tool",
    ".flutter-plugins",
    ".flutter-plugins-dependencies",
    "android",
    "ios",
    "linux",
    "macos",
    "windows",
    "web",
    # Gradle / Maven
    ".gradle",
    ".idea",
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
    # Flutter / Dart
    "pubspec.yaml",
    "pubspec.lock",
    # iOS / macOS
    "Podfile",
    # Rust
    "Cargo.toml",
    # Elixir
    "mix.exs",
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
_DEP_NAME_RE = re.compile(r'^([A-Za-z0-9][A-Za-z0-9_\-\.]*)')

_CAPABILITY_KEYWORDS: dict[str, list[str]] = {
    "payments":  ["stripe", "paypal", "braintree", "square", "razorpay", "adyen", "mollie", "checkout"],
    "email":     ["sendgrid", "mailgun", "nodemailer", "resend", "postmark", "mandrill", "sparkpost", "ses"],
    "auth":      ["jwt", "passport", "auth0", "clerk", "supabase", "pyjwt", "python-jose", "argon2", "bcrypt", "devise", "guardian",
                  "firebase_auth", "firebase-auth", "amplify_auth"],
    "database":  ["sqlalchemy", "psycopg2", "psycopg", "asyncpg", "pymongo", "motor", "mongoose", "prisma",
                  "sequelize", "typeorm", "gorm", "diesel", "ecto", "activerecord", "hibernate", "mybatis",
                  "cloud_firestore", "firebase_database", "firestore"],
    "storage":   ["boto3", "s3", "cloudinary", "multer", "minio", "gcs", "azure-storage",
                  "firebase_storage", "amplify_storage"],
    "queue":     ["celery", "rq", "bull", "rabbitmq", "kafka", "sidekiq", "oban", "delayed_job"],
    "search":    ["elasticsearch", "meilisearch", "algolia", "typesense", "opensearch"],
    "cache":     ["redis", "memcached", "aioredis", "ioredis"],
    "firebase":  ["firebase_core", "firebase_auth", "cloud_firestore", "firebase_storage",
                  "firebase_messaging", "firebase_database", "firebase-admin", "firebase"],
}


def _iter_files(root: Path):
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in _IGNORE_DIRS for part in p.parts):
            continue
        yield p


def _extract_dependencies(root: Path) -> list[str]:
    """
    Extract raw dependency/package names from whatever manifest files exist.
    No interpretation, just facts. The LLM handles what each dep means.
    """
    deps: list[str] = []
    seen: set[str] = set()

    def add(raw: str):
        raw = raw.strip()
        m = _DEP_NAME_RE.match(raw)
        if not m:
            return
        name = m.group(1).lower()
        if name and len(name) >= 2 and name not in seen:
            seen.add(name)
            deps.append(name)

    # --- requirements*.txt (Python) ---
    for rname in ("requirements.txt", "requirements-dev.txt", "requirements/base.txt",
                  "requirements/production.txt", "requirements/common.txt"):
        fp = root / rname
        if fp.exists():
            for line in fp.read_text(errors="ignore").splitlines():
                line = line.strip()
                if not line or line.startswith(("#", "-", ".")):
                    continue
                add(re.split(r"[>=<!~^@\[\s;]", line)[0])

    # --- pyproject.toml (Python, TOML: regex, no extra dep needed) ---
    fp = root / "pyproject.toml"
    if fp.exists():
        text = fp.read_text(errors="ignore")
        # PEP 621: dependencies = ["pkg>=x", ...]  or poetry style
        for m in re.finditer(r'["\']([A-Za-z0-9][A-Za-z0-9_\-\.]+)\s*(?:[>=<!~^,\[\s"\'\\])', text):
            add(m.group(1))

    # --- Pipfile (Python) ---
    fp = root / "Pipfile"
    if fp.exists():
        for line in fp.read_text(errors="ignore").splitlines():
            m = re.match(r'^([A-Za-z0-9][A-Za-z0-9_\-\.]*)\s*=', line.strip())
            if m and m.group(1).lower() not in ("python_requires", "python_version", "python"):
                add(m.group(1))

    # --- package.json (Node/JS/TS) ---
    fp = root / "package.json"
    if fp.exists():
        try:
            import json as _json
            data = _json.loads(fp.read_text(errors="ignore"))
            for section in ("dependencies", "devDependencies", "peerDependencies"):
                for name in data.get(section, {}):
                    # @scope/pkg → pkg (also keep full name)
                    clean = name.lstrip("@").split("/")[-1]
                    add(clean)
        except Exception:
            pass

    # --- go.mod (Go) ---
    fp = root / "go.mod"
    if fp.exists():
        in_require = False
        for line in fp.read_text(errors="ignore").splitlines():
            s = line.strip()
            if s.startswith("require ("):
                in_require = True
                continue
            if in_require:
                if s == ")":
                    in_require = False
                    continue
                parts = s.split()
                if parts:
                    add(parts[0].split("/")[-1])  # github.com/gin-gonic/gin → gin
            elif s.startswith("require "):
                parts = s.split()
                if len(parts) >= 2:
                    add(parts[1].split("/")[-1])

    # --- Cargo.toml (Rust) ---
    fp = root / "Cargo.toml"
    if fp.exists():
        in_deps = False
        for line in fp.read_text(errors="ignore").splitlines():
            s = line.strip()
            if s in ("[dependencies]", "[dev-dependencies]", "[build-dependencies]"):
                in_deps = True
                continue
            if in_deps:
                if s.startswith("["):
                    in_deps = False
                    continue
                if "=" in s:
                    add(s.split("=")[0].strip())

    # --- Gemfile (Ruby) ---
    fp = root / "Gemfile"
    if fp.exists():
        for line in fp.read_text(errors="ignore").splitlines():
            m = re.match(r"""\s*gem\s+['"]([^'"]+)['"]""", line)
            if m:
                add(m.group(1))

    # --- pom.xml (Java/Maven) ---
    fp = root / "pom.xml"
    if fp.exists():
        for m in re.finditer(r"<artifactId>([^<]+)</artifactId>", fp.read_text(errors="ignore")):
            add(m.group(1))

    # --- build.gradle / build.gradle.kts (Java/Kotlin/Gradle) ---
    for gname in ("build.gradle", "build.gradle.kts"):
        fp = root / gname
        if fp.exists():
            for m in re.finditer(
                r"""(?:implementation|api|compile|testImplementation|runtimeOnly)\s*[(\s]*['"]([^'"]+)['"]""",
                fp.read_text(errors="ignore"),
            ):
                parts = m.group(1).split(":")
                if len(parts) >= 2:
                    add(parts[1])

    # --- composer.json (PHP) ---
    fp = root / "composer.json"
    if fp.exists():
        try:
            import json as _json
            data = _json.loads(fp.read_text(errors="ignore"))
            for section in ("require", "require-dev"):
                for name in data.get(section, {}):
                    if name.lower() != "php":
                        add(name.split("/")[-1])
        except Exception:
            pass

    # --- mix.exs (Elixir) ---
    fp = root / "mix.exs"
    if fp.exists():
        for m in re.finditer(r"\{:([a-z_]+),", fp.read_text(errors="ignore")):
            add(m.group(1))

    # --- pubspec.yaml (Dart/Flutter) ---
    fp = root / "pubspec.yaml"
    if fp.exists():
        in_deps = False
        for line in fp.read_text(errors="ignore").splitlines():
            s = line.strip()
            if s in ("dependencies:", "dev_dependencies:"):
                in_deps = True
                continue
            if in_deps:
                if s and not s.startswith(" ") and not s.startswith("\t") and s.endswith(":"):
                    in_deps = False
                    continue
                m = re.match(r"([a-z][a-z0-9_]*):", s)
                if m and m.group(1) not in ("sdk",):
                    add(m.group(1))

    # --- *.csproj / *.fsproj (C# / F# / .NET) ---
    for proj_file in root.glob("*.csproj"):
        for m in re.finditer(r'Include="([^"]+)"', proj_file.read_text(errors="ignore")):
            parts = m.group(1).split(".")
            add(parts[-1] if len(parts) > 1 else m.group(1))
        break  # just the first one near root
    for proj_file in root.glob("*.fsproj"):
        for m in re.finditer(r'Include="([^"]+)"', proj_file.read_text(errors="ignore")):
            add(m.group(1).split(".")[-1])
        break

    return deps


def _detect_capability_from_deps(deps: list[str]) -> dict[str, list[str]]:
    """Infer capabilities from dep names: no code scanning needed."""
    dep_set = set(deps)
    evidence: dict[str, list[str]] = {}
    for cap, keywords in _CAPABILITY_KEYWORDS.items():
        matched = [kw for kw in keywords if any(kw in d or d in kw for d in dep_set)]
        if matched:
            evidence[cap] = matched
    return evidence


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

    deps = _extract_dependencies(root)
    capability_evidence = _detect_capability_from_deps(deps)

    return {
        "languages": languages,
        "language_rank": language_rank,
        "language_counts": dict(lang_counts),
        "primary_language": primary_language,
        "entrypoints_near_root": ep_root,
        "entrypoints_anywhere": ep_any,
        "entrypoints": ep_root,
        "monorepo_hint": monorepo_hint,
        "manifest_paths": manifest_paths[:30],
        "routes_sample": routes_sample2[:20],
        "dependencies": deps,
        "framework_hints": deps,   # alias: sanitizer uses this key
        "capability_evidence": capability_evidence,
    }