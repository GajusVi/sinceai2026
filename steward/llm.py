from __future__ import annotations

import json
import re
from typing import Union

from .config import Settings

DEFAULT_MODELS = {"claude": "claude-haiku-5-5", "gemini": "gemini-2.5-flash"}


class ClaudeClient:
    """Anthropic Claude. Has no embeddings API, so semantic search keeps the offline embedder."""

    provider = "claude"
    supports_embeddings = False

    def __init__(self, api_key: str, model: str):
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def _complete(self, prompt: str, max_tokens: int = 1024) -> str:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in response.content if block.type == "text").strip()

    def generate_json(self, prompt: str) -> dict:
        text = self._complete(prompt + "\n\nReply with a single JSON object and nothing else.")
        match = re.search(r"\{.*\}", text, re.DOTALL)  # tolerate ```json fences or stray words
        return json.loads(match.group(0) if match else text)

    def generate_text(self, prompt: str) -> str:
        return self._complete(prompt)

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("Claude has no embeddings API")


class GeminiClient:
    provider = "gemini"
    supports_embeddings = True

    def __init__(self, api_key: str, model: str, embedding_model: str):
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self.model = model
        self.embedding_model = embedding_model

    def generate_json(self, prompt: str) -> dict:
        response = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
            config={"response_mime_type": "application/json", "temperature": 0},
        )
        return json.loads(response.text)

    def generate_text(self, prompt: str) -> str:
        response = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
            config={"temperature": 0.2},
        )
        return response.text.strip()

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self._client.models.embed_content(model=self.embedding_model, contents=texts)
        return [e.values for e in response.embeddings]


LLMClient = Union[ClaudeClient, GeminiClient]


def get_llm(settings: Settings) -> LLMClient | None:
    if not settings.llm_enabled:
        return None
    provider = settings.provider
    model = settings.llm_model or DEFAULT_MODELS.get(provider or "", "")
    try:
        if provider == "claude":
            return ClaudeClient(settings.anthropic_api_key, model)
        if provider == "gemini":
            return GeminiClient(settings.gemini_api_key, model, settings.embedding_model)
    except ImportError:
        return None
    return None
