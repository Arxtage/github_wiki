import asyncio
from pathlib import PurePosixPath

import httpx

from app.github_client import fetch_file_content

SKIP_DIRS = {
    "node_modules", ".git", "vendor", "dist", "build", "__pycache__", ".venv",
    "venv", "env", ".idea", ".vscode", ".mypy_cache", ".pytest_cache",
    ".tox", ".eggs", ".gradle", "target", "out", "bin", "obj",
    ".next", ".nuxt", ".svelte-kit", "coverage", ".turbo",
}

SKIP_EXTENSIONS = {
    # Images
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".bmp", ".tiff",
    # Audio/Video
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".flac", ".ogg", ".webm",
    # Archives
    ".zip", ".tar", ".gz", ".bz2", ".rar", ".7z", ".xz",
    # Binaries
    ".exe", ".dll", ".so", ".dylib", ".bin", ".o", ".a", ".class", ".pyc",
    # Data/Lock
    ".lock", ".db", ".sqlite", ".sqlite3", ".pkl", ".pickle",
    # Maps/Minified
    ".min.js", ".min.css", ".map",
    # Fonts
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    # Other
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
}

SKIP_FILENAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "Pipfile.lock", "go.sum", "Gemfile.lock", "composer.lock",
    "cargo.lock", ".DS_Store", "Thumbs.db",
}

MAX_FILE_SIZE = 100_000  # 100KB

README_NAMES = {"readme", "readme.md", "readme.txt", "readme.rst"}

MANIFEST_NAMES = {
    "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
    "package.json", "cargo.toml", "go.mod", "go.sum", "gemfile",
    "composer.json", "pom.xml", "build.gradle", "build.gradle.kts",
    "mix.exs", "project.clj", "stack.yaml", "cabal.project",
    "pubspec.yaml", "shard.yml", "makefile", "cmakelists.txt",
}

CI_INFRA_NAMES = {
    "dockerfile", "docker-compose.yml", "docker-compose.yaml",
    ".env.example", "nginx.conf", "vercel.json", "netlify.toml",
    "fly.toml", "render.yaml", "procfile", "terraform.tf",
}

ENTRY_POINT_STEMS = {"main", "app", "index", "server", "cli", "manage", "__main__"}

SOURCE_DIRS = {"src", "lib", "app", "cmd", "pkg", "internal", "core"}


def _in_skip_dir(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return any(p in SKIP_DIRS for p in parts)


def _has_skip_ext(path: str) -> bool:
    lower = path.lower()
    return any(lower.endswith(ext) for ext in SKIP_EXTENSIONS)


def _assign_priority(path: str) -> int:
    name = PurePosixPath(path).name.lower()
    stem = PurePosixPath(path).stem.lower()

    if name in README_NAMES:
        return 0
    if name in MANIFEST_NAMES:
        return 1

    # CI/Infra
    if name in CI_INFRA_NAMES:
        return 2
    parts = PurePosixPath(path).parts
    if any(p == ".github" for p in parts):
        return 2

    # Source code — entry points or top-level / standard source dirs
    depth = len(parts)
    in_source_dir = any(p.lower() in SOURCE_DIRS for p in parts)
    is_entry = stem in ENTRY_POINT_STEMS

    if is_entry and (depth <= 2 or in_source_dir):
        return 3
    if in_source_dir or depth <= 2:
        return 3

    return 4


def filter_tree(blobs: list[dict]) -> list[dict]:
    """Filter blobs and return sorted by priority."""
    filtered = []
    for blob in blobs:
        path = blob["path"]
        size = blob.get("size", 0)

        if _in_skip_dir(path):
            continue
        if _has_skip_ext(path):
            continue
        if PurePosixPath(path).name in SKIP_FILENAMES:
            continue
        if size > MAX_FILE_SIZE:
            continue

        blob["_priority"] = _assign_priority(path)
        filtered.append(blob)

    filtered.sort(key=lambda b: (b["_priority"], b["path"]))
    return filtered


def build_tree_string(blobs: list[dict]) -> str:
    """Build a directory tree representation from blob paths."""
    lines = []
    for blob in blobs:
        depth = blob["path"].count("/")
        indent = "  " * depth
        name = PurePosixPath(blob["path"]).name
        lines.append(f"{indent}{name}")
    return "\n".join(lines)


async def build_context(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    branch: str,
    blobs: list[dict],
    max_chars: int,
) -> str:
    """Fetch file contents respecting the context budget."""
    filtered = filter_tree(blobs)
    if not filtered:
        return ""

    tree_str = build_tree_string(filtered)
    context_parts: list[str] = [f"## Directory Structure\n\n```\n{tree_str}\n```\n"]
    used = len(context_parts[0])

    sem = asyncio.Semaphore(10)

    async def _fetch(path: str) -> tuple[str, str | None]:
        async with sem:
            content = await fetch_file_content(client, owner, repo, branch, path)
            return path, content

    tasks = [_fetch(b["path"]) for b in filtered]
    results = dict(await asyncio.gather(*tasks))

    for blob in filtered:
        path = blob["path"]
        content = results.get(path)
        if content is None:
            continue

        priority = blob["_priority"]
        section = f"\n## {path}\n\n```\n{content}\n```\n"
        section_len = len(section)

        if used + section_len > max_chars:
            if priority <= 1:
                # Truncate high-priority files rather than skip
                remaining = max_chars - used - len(f"\n## {path}\n\n```\n") - len("\n... (truncated)\n```\n")
                if remaining > 200:
                    section = f"\n## {path}\n\n```\n{content[:remaining]}\n... (truncated)\n```\n"
                    context_parts.append(section)
                    used += len(section)
                break
            else:
                break

        context_parts.append(section)
        used += section_len

    return "".join(context_parts)
