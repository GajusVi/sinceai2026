import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
# Same .env as the rest of the repo (keys, provider). Real environment variables win.
load_dotenv(ROOT_DIR / ".env", override=False)


def _backend_ready() -> bool:
    """True when the shared backend client (LLM_PROVIDER in .env: gemini | aitta | ollama ...) has a key and model."""
    try:
        from backend.config import get_settings

        return get_settings().llm_ready()
    except Exception:
        return False


@dataclass(frozen=True)
class Settings:
    catalog_dir: Path
    data_dir: Path
    prompts_dir: Path
    as_of: date | None
    gemini_api_key: str | None
    use_llm: str
    llm_model: str | None
    embedding_model: str
    anthropic_api_key: str | None = None
    llm_provider: str = "auto"

    @classmethod
    def from_env(cls) -> "Settings":
        as_of = os.getenv("STEWARD_AS_OF")
        return cls(
            catalog_dir=Path(os.getenv("STEWARD_CATALOG_DIR", ROOT_DIR / "catalog")),
            data_dir=Path(os.getenv("STEWARD_DATA_DIR", ROOT_DIR / "data" / "steward")),
            prompts_dir=Path(os.getenv("STEWARD_PROMPTS_DIR", ROOT_DIR / "prompts")),
            as_of=date.fromisoformat(as_of) if as_of else None,
            gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
            use_llm=os.getenv("STEWARD_USE_LLM", "auto").lower(),
            llm_model=os.getenv("STEWARD_LLM_MODEL") or None,
            embedding_model=os.getenv("STEWARD_EMBEDDING_MODEL", "gemini-embedding-001"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
            llm_provider=os.getenv("STEWARD_LLM_PROVIDER", "auto").lower(),
        )

    @property
    def provider(self) -> str | None:
        """Which LLM to use: the one asked for, else Claude, else Gemini, depending on which key is set."""
        if self.llm_provider == "claude":
            return "claude" if self.anthropic_api_key else None
        if self.llm_provider == "gemini":
            return "gemini" if self.gemini_api_key else None
        if self.llm_provider == "backend":
            return "backend" if _backend_ready() else None
        if self.anthropic_api_key:
            return "claude"
        return "backend" if _backend_ready() else None

    @property
    def llm_enabled(self) -> bool:
        return self.use_llm != "off" and self.provider is not None


# Decision thresholds. Tune them against tests/golden_questions.json.
REUSE_MIN_COVERAGE = 1.0
REUSE_MIN_TRUST = 0.6
EXTEND_MIN_COVERAGE = 0.5

STALE_AFTER_DAYS = 90
LOW_USAGE_VIEWS = 5
DUPLICATE_THRESHOLD = 0.6

# Words that carry no analytics meaning. Any other word in a question that no dictionary term covers goes to
# ParsedQuestion.unmapped_terms and turns the verdict into CLARIFY (no silent drops). Grow this list, never the goldens.
STOPWORDS = frozenset(
    """
    a an the and or of in on at to for by with from per across over vs versus via about into than then as
    is are was were be been do does did have has had it its this that these those there their them they
    i me my we us our you your what which who how why when where many much any all each every some more most
    need needs want wants like would could should can will please show shows showing give tell list display see
    create build make new get find look compare comparison view views
    dashboard dashboards report reports management monthly quarterly weekly yearly annual daily global country
    countries level levels overview analysis data current latest last year years quarter month months week
    something anything thing things interesting
    trial logistic logistics footprint
    """.split()
)
