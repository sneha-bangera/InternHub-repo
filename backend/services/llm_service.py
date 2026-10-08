import json

import httpx
from pydantic import ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from backend.api.target_schemas import JDParseResult
from backend.core.config import settings


class LLMConfigurationError(Exception):
    pass


class LLMServiceError(Exception):
    pass


class RetryableLLMError(Exception):
    pass


class LLMService:
    _PROVIDERS = {
        "groq": (
            "https://api.groq.com/openai/v1/chat/completions",
            "GROQ_API_KEY",
            "GROQ_MODEL",
        ),
        "openai": (
            "https://api.openai.com/v1/chat/completions",
            "OPENAI_API_KEY",
            "OPENAI_MODEL",
        ),
    }

    def parse_job_description(self, jd_text: str) -> JDParseResult:
        provider = settings.LLM_PROVIDER.lower()
        provider_config = self._PROVIDERS.get(provider)
        if provider_config is None:
            raise LLMConfigurationError(f"Unsupported LLM provider: {provider}")
        endpoint, key_setting, model_setting = provider_config
        api_key = getattr(settings, key_setting)
        if not api_key:
            raise LLMConfigurationError(f"{key_setting} is required for LLM parsing")

        try:
            return self._request_parse(endpoint, api_key, getattr(settings, model_setting), jd_text)
        except (LLMConfigurationError, LLMServiceError):
            raise
        except Exception as exc:
            raise LLMServiceError("Job description parsing failed after retries") from exc

    @retry(
        stop=stop_after_attempt(settings.LLM_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(
            (
                httpx.TimeoutException,
                httpx.TransportError,
                RetryableLLMError,
                ValidationError,
                json.JSONDecodeError,
            )
        ),
        reraise=True,
    )
    def _request_parse(
        self, endpoint: str, api_key: str, model: str, jd_text: str
    ) -> JDParseResult:
        response = httpx.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Extract job requirements from the supplied job description. "
                            "Return a JSON object with role_title, seniority, required_skills, "
                            "preferred_skills, and keywords. Use null or empty arrays when "
                            "the description does not explicitly provide a value. Do not "
                            "invent requirements or infer unstated details."
                        ),
                    },
                    {"role": "user", "content": jd_text},
                ],
            },
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )
        if response.status_code == 429 or response.status_code >= 500:
            raise RetryableLLMError(f"LLM provider returned HTTP {response.status_code}")
        if response.is_error:
            raise LLMServiceError(f"LLM provider returned HTTP {response.status_code}")

        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        return JDParseResult.model_validate_json(content)


llm_service = LLMService()
