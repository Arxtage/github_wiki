from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.content_processor import build_context
from app.exceptions import EmptyRepoError, GitHubFetchError, LLMError
from app.github_client import fetch_repo_tree
from app.llm import generate_summary
from app.schemas import ErrorResponse, SummarizeRequest, SummarizeResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    headers = {"Accept": "application/vnd.github+json"}
    if settings.GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"

    app.state.http_client = httpx.AsyncClient(
        headers=headers,
        timeout=httpx.Timeout(30.0),
        follow_redirects=True,
    )
    yield
    await app.state.http_client.aclose()


app = FastAPI(
    title="GitHub Repository Summarizer",
    description="Analyzes a GitHub repository and returns an LLM-generated summary.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(GitHubFetchError)
async def github_fetch_handler(_: Request, exc: GitHubFetchError):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(message=exc.message).model_dump(),
    )


@app.exception_handler(LLMError)
async def llm_handler(_: Request, exc: LLMError):
    return JSONResponse(
        status_code=502,
        content=ErrorResponse(message=exc.message).model_dump(),
    )


@app.exception_handler(EmptyRepoError)
async def empty_repo_handler(_: Request, exc: EmptyRepoError):
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(message=exc.message).model_dump(),
    )


@app.exception_handler(httpx.TimeoutException)
async def timeout_handler(_: Request, exc: httpx.TimeoutException):
    return JSONResponse(
        status_code=502,
        content=ErrorResponse(message="Timed out connecting to GitHub").model_dump(),
    )


@app.exception_handler(Exception)
async def generic_handler(_: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(message="Internal server error").model_dump(),
    )


@app.post("/summarize", response_model=SummarizeResponse)
async def summarize(request: SummarizeRequest):
    owner, repo = request.owner_repo()
    client: httpx.AsyncClient = app.state.http_client

    branch, blobs = await fetch_repo_tree(client, owner, repo)

    context = await build_context(
        client, owner, repo, branch, blobs, settings.MAX_CONTEXT_CHARS,
    )

    if not context.strip():
        raise EmptyRepoError()

    return await generate_summary(context)
