from dotenv import load_dotenv
load_dotenv()

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    DEEPSEEK_API_KEY: str = "sk-e8bda1699430447e97c0d6fcbe83471a"


    DEEPSEEK_MODEL: str = "deepseek-v4-flash"
    # The complex report-narrative generation (a big JSON: prose + KPIs + several sheets)
    # makes v4-flash spend its ENTIRE 32 K output budget reasoning and return EMPTY content
    # (finish_reason=length -> "Empty model response" -> 502). v4-pro finishes its reasoning
    # and writes the answer (finish_reason=stop). Used for the narrative and as the fallback
    # whenever flash comes back empty.
    DEEPSEEK_HEAVY_MODEL: str = "deepseek-v4-pro"
    # ── The narrative (what the Word and PDF reports are written from) ────────────
    # This is the one expensive call in the pipeline, and it does not have to run on the
    # same provider as the cheap cell-fill and agent calls. Set these three in .env to
    # send it elsewhere — e.g. OpenAI:
    #
    #   HEAVY_API_KEY=sk-...
    #   HEAVY_BASE_URL=https://api.openai.com/v1
    #   HEAVY_MODEL=gpt-4.1
    #
    # Leave HEAVY_API_KEY blank and everything stays on DeepSeek exactly as before.
    # The client is built with the OpenAI SDK either way, so no new dependency is needed.
    HEAVY_API_KEY: str = ""
    HEAVY_BASE_URL: str = ""
    HEAVY_MODEL: str = ""
    # Setting the conventional OPENAI_API_KEY is enough on its own: it implies OpenAI's
    # endpoint and OPENAI_MODEL (default gpt-4.1). The HEAVY_* trio still wins if given,
    # so any other provider can be pointed at without touching this.
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4.1"
    # Cover artwork generated per project. Falls back to dall-e-3, then to the bundled
    # industry photograph, so an unavailable model never breaks a report.
    OPENAI_IMAGE_MODEL: str = "gpt-image-1"
    _OPENAI_BASE = "https://api.openai.com/v1"

    @property
    def _use_openai(self) -> bool:
        return bool(self.OPENAI_API_KEY.strip()) and not self.HEAVY_API_KEY.strip()

    @property
    def heavy_api_key(self) -> str:
        return (self.HEAVY_API_KEY.strip() or self.OPENAI_API_KEY.strip()
                or self.DEEPSEEK_API_KEY)

    @property
    def heavy_base_url(self) -> str:
        if self.HEAVY_BASE_URL.strip():
            return self.HEAVY_BASE_URL.strip()
        return self._OPENAI_BASE if self._use_openai else "https://api.deepseek.com"

    @property
    def heavy_model(self) -> str:
        if self.HEAVY_MODEL.strip():
            return self.HEAVY_MODEL.strip()
        return self.OPENAI_MODEL.strip() if self._use_openai else self.DEEPSEEK_HEAVY_MODEL

    @property
    def heavy_is_separate(self) -> bool:
        """True when the narrative runs somewhere other than the default DeepSeek client."""
        return bool(self.HEAVY_API_KEY.strip() or self.HEAVY_BASE_URL.strip()
                    or self.HEAVY_MODEL.strip() or self.OPENAI_API_KEY.strip())
    SECRET_KEY: str = "changeme"
    RESEND_API_KEY: str = ""
    FROM_EMAIL: str = "onboarding@resend.dev"
    FROM_NAME: str = "Smart Project Blueprint"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    class Config:
        env_file = ".env"

settings = Settings()
