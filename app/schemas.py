import re

from pydantic import BaseModel, field_validator

_GITHUB_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)/?$"
)


class SummarizeRequest(BaseModel):
    github_url: str

    @field_validator("github_url")
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        v = v.rstrip("/")
        if not _GITHUB_RE.match(v):
            raise ValueError("Invalid GitHub repository URL")
        return v

    def owner_repo(self) -> tuple[str, str]:
        m = _GITHUB_RE.match(self.github_url)
        assert m is not None
        return m.group("owner"), m.group("repo")


class SummarizeResponse(BaseModel):
    summary: str
    technologies: list[str]
    structure: str


class ErrorResponse(BaseModel):
    status: str = "error"
    message: str
