# GitHub Repository Summarizer API

A FastAPI service that takes a GitHub repository URL, fetches its contents, and returns an LLM-generated summary including what the project does, its tech stack, and how it's structured.

## Quick Start

### Prerequisites

- Python 3.11+
- A [Gemini API key](https://aistudio.google.com/apikey)
- (Optional) A [GitHub personal access token](https://github.com/settings/tokens) for higher rate limits

### Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configuration

```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
# Optionally add GITHUB_TOKEN for higher rate limits (5000 vs 60 req/hr)
```

### Run

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

## Usage

```bash
curl -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d '{"github_url": "https://github.com/psf/requests"}'
```

### Response

```json
{
  "summary": "Requests is an elegant and simple HTTP library for Python...",
  "technologies": ["Python", "urllib3", "certifi", "charset-normalizer", "pytest"],
  "structure": "The project follows a standard Python package layout..."
}
```

### Error Responses

| Status | Scenario |
|--------|----------|
| 422 | Invalid GitHub URL or empty repository |
| 404 | Repository not found or private |
| 429 | GitHub API rate limit exceeded |
| 502 | GitHub timeout or LLM service failure |

## Design Decisions

### Model Choice: Gemini 2.5 Flash

- **1M token context window** — handles large repositories without aggressive truncation
- **Native structured JSON output** — `response_mime_type="application/json"` with schema validation eliminates fragile regex parsing
- **Fast and cost-effective** — ideal for a summarization API that needs quick responses

### Content Prioritization

Not all files are equally useful for understanding a repository. The processor assigns priority tiers:

| Priority | Files | Rationale |
|----------|-------|-----------|
| 0 | README files | Best single-source summary |
| 1 | Package manifests (`package.json`, `pyproject.toml`, etc.) | Reveals tech stack |
| 2 | CI/Infrastructure (`Dockerfile`, GitHub Actions, etc.) | Architecture signals |
| 3 | Source code (entry points first, then by directory depth) | Core logic |
| 4 | Other docs and configs | Supporting context |

### File Filtering

Skips files that add noise without insight:
- Binary files, images, fonts, archives
- Lock files (`package-lock.json`, `yarn.lock`, etc.)
- Build artifacts (`dist/`, `build/`, `node_modules/`)
- Files larger than 100KB

### Context Budget

An 800,000 character budget (~200K tokens) ensures the prompt stays well within Gemini's context window while leaving room for the system prompt and response. High-priority files (README, manifests) are truncated rather than skipped; lower-priority files are dropped when the budget is exhausted.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | Yes | — | Google Gemini API key |
| `GITHUB_TOKEN` | No | — | GitHub PAT for higher rate limits |
| `GEMINI_MODEL` | No | `gemini-2.5-flash` | Gemini model to use |
| `MAX_CONTEXT_CHARS` | No | `800000` | Max characters sent to the LLM |

## Project Structure

```
github_wiki/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, endpoint, exception handlers
│   ├── config.py             # Settings via pydantic-settings
│   ├── schemas.py            # Pydantic request/response models
│   ├── github_client.py      # Async GitHub API fetching
│   ├── content_processor.py  # File filtering + context prioritization
│   ├── llm.py                # Gemini API integration + prompt
│   └── exceptions.py         # Custom exceptions
```
