from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    GEMINI_API_KEY: str
    GITHUB_TOKEN: str | None = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    MAX_CONTEXT_CHARS: int = 800_000

    model_config = {"env_file": ".env"}


settings = Settings()
