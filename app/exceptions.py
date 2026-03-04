class GitHubFetchError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class LLMError(Exception):
    def __init__(self, message: str = "LLM service unavailable"):
        self.message = message
        super().__init__(message)


class EmptyRepoError(Exception):
    def __init__(
        self, message: str = "Repository is empty or contains no analyzable files",
    ):
        self.message = message
        super().__init__(message)
