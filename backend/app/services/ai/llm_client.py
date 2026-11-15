import json
from typing import Any

import httpx

from app.config import settings


class LLMConfigurationError(RuntimeError):
    pass


class LLMRequestError(RuntimeError):
    pass


class LLMResponseError(RuntimeError):
    pass


class LLMClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.LLM_API_KEY
        self.base_url = (base_url or settings.LLM_BASE_URL).rstrip("/")
        self.model = model or settings.LLM_MODEL
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.LLM_TIMEOUT_SECONDS
        )
        self.transport = transport

    async def complete_json(
        self, *, system_prompt: str, user_prompt: str
    ) -> dict[str, Any]:
        if not self.api_key:
            raise LLMConfigurationError("LLM_API_KEY is not configured")

        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.post(url, headers=headers, json=body)
        except httpx.TimeoutException as exc:
            raise LLMRequestError("LLM request timed out") from exc
        except httpx.HTTPError as exc:
            raise LLMRequestError("Could not reach the LLM provider") from exc

        if response.is_error:
            raise LLMRequestError(
                f"LLM provider returned HTTP {response.status_code}"
            )

        try:
            response_body = response.json()
            content = response_body["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise TypeError("message content is not a string")
            parsed_content = json.loads(content)
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMResponseError(
                "LLM provider returned an invalid JSON response"
            ) from exc

        if not isinstance(parsed_content, dict):
            raise LLMResponseError("LLM output must be a JSON object")
        return parsed_content
