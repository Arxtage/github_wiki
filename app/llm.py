from google import genai
from google.genai import types

from app.config import settings
from app.exceptions import LLMError
from app.schemas import SummarizeResponse

SYSTEM_PROMPT = """\
You are a senior software engineer analyzing a GitHub repository.
You will receive the repository's directory structure and file contents.

Produce a JSON object with exactly these fields:

- "summary": A clear, concise paragraph (3-6 sentences) explaining what the project does, \
its purpose, and key features. Write for a developer audience.

- "technologies": A flat list of technologies, languages, frameworks, and notable libraries \
used in the project. Be specific (e.g., "FastAPI" not just "Python web framework"). \
Only list technologies you can confirm from the code and config files.

- "structure": A brief description (2-4 sentences) of how the project is organized — \
key directories, entry points, and architectural patterns you observe.

Rules:
- Only describe what you can directly observe in the provided files. Do not speculate.
- If a file was truncated, note that your analysis of it may be incomplete.
- Be factual and precise. Avoid marketing language.\
"""


async def generate_summary(context: str) -> SummarizeResponse:
    """Call Gemini to generate a structured repository summary."""
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    config = types.GenerateContentConfig(
        temperature=0.2,
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=SummarizeResponse,
    )

    for attempt in range(2):
        try:
            response = await client.aio.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=context,
                config=config,
            )

            if not response.text:
                if attempt == 0:
                    continue
                raise LLMError("Empty response from LLM")

            return SummarizeResponse.model_validate_json(response.text)

        except LLMError:
            raise
        except Exception as exc:
            if attempt == 0:
                continue
            raise LLMError(f"Failed to parse LLM response: {exc}") from exc

    raise LLMError("Failed to generate summary after retries")
