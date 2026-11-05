"""All runtime settings come from env vars or .env. Swap LLM provider with one line: LLM_PROVIDER=..."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent

# provider -> (base_url, env var holding the key, default model)
PROVIDERS: dict[str, tuple[str, str | None, str | None]] = {
    "anthropic": ("https://api.anthropic.com/v1/", "ANTHROPIC_API_KEY", "claude-sonnet-5-5"),
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY", None),  # set LLM_MODEL yourself
    "aitta": ("https://aitta-api.csc.fi/openai/v1", "AITTA_API_KEY", "meta-llama/Llama-3.3-70B-Instruct"),
    "featherless": ("https://api.featherless.ai/v1", "FEATHERLESS_API_KEY", None),  # $25 Since AI credit
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY", "gemini-3.5-flash"),  # MLH Gemini prize
    "ollama": ("http://localhost:11434/v1", None, "llama3.2:3b"),
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    llm_provider: str = "anthropic"
    llm_model: str | None = None
    # per-provider model, used when LLM_MODEL is blank, so switching LLM_PROVIDER is one line
    anthropic_model: str | None = None
    openai_model: str | None = None
    aitta_model: str | None = None
    featherless_model: str | None = None
    gemini_model: str | None = None
    ollama_model: str | None = None
    llm_base_url: str | None = None  # overrides the provider default
    llm_api_key: str | None = None  # overrides the provider key
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    aitta_api_key: str | None = None
    featherless_api_key: str | None = None
    gemini_api_key: str | None = None
    llm_timeout_s: float = 45.0
    llm_max_retries: int = 2  # SDK-level retries with backoff (429/5xx/timeouts)
    llm_workers: int = 2  # parallel LLM calls; free tiers rate-limit bursts
    llm_max_tokens: int = 4000  # Gemini 3 always reasons; thinking tokens count here

    demo_mode: bool = False  # replay cached outputs; never calls the network
    db_path: Path = ROOT / "data" / "app.db"
    embed_model: str = "BAAI/bge-small-en-v1.5"
    user_role: str = "the support team lead"  # who the product serves; change HERE on Friday (part of the cache key)

    def resolved(self) -> tuple[str, str, str | None]:
        """Return (base_url, api_key, model) for the active provider."""
        if self.llm_provider not in PROVIDERS and not self.llm_base_url:
            raise ValueError(f"Unknown LLM_PROVIDER={self.llm_provider!r}; set LLM_BASE_URL too")
        base, key_env, default_model = PROVIDERS.get(self.llm_provider, (None, None, None))
        key = self.llm_api_key or (getattr(self, key_env.lower(), None) if key_env else None)
        per_provider = getattr(self, f"{self.llm_provider}_model", None)
        return (self.llm_base_url or base, key or "not-needed", self.llm_model or per_provider or default_model)

    def llm_ready(self) -> bool:
        _, key, model = self.resolved()
        return bool(model) and (key != "not-needed" or self.llm_provider == "ollama")


@lru_cache
def get_settings() -> Settings:
    return Settings()
