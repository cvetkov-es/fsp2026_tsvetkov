from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Переменные окружения. Корневой .env проекта тоже читается (../.env)."""

    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str = "postgresql+psycopg://fsp:fsp@localhost:5432/fsp"
    secret_key: str = "dev-secret-change-me"
    demo_mode: bool = False  # включается явно: DEMO_MODE=true
    public_base_url: str = "http://localhost:5173"
    cookie_secure: bool = False

    llm_base_url: str | None = Field(
        default=None, validation_alias=AliasChoices("LLM_BASE_URL", "OPENROUTER_BASE_URL")
    )
    llm_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("LLM_API_KEY", "OPENROUTER_API_KEY")
    )
    llm_profile: Literal["dev", "prod"] = "dev"
    # Переопределение моделей (техдизайн §9); по умолчанию — маршрут профиля из app/llm/config.py
    llm_model_pd: str | None = None
    llm_model_pd_fallback: str | None = None
    llm_model_runtime: str | None = None
    ner_enabled: bool = True  # NER natasha в подпроцессе; false — только эвристика первых строк
    # Офлайн-задачи лаборатории без ПДн (техдизайн §9): решатель банка двумя семействами моделей и судья подбора
    llm_model_solver_a: str = "deepseek/deepseek-v4.1-flash"
    llm_model_solver_b: str = "google/gemini-3.8-flash"
    llm_model_judge: str = "google/gemini-3.8-flash"
    llm_model_ai_policy: str = "deepseek/deepseek-v4.1-flash"  # политика «только ИИ» в лаборатории «Работы с ИИ»

    mail_host: str | None = None
    mail_port: int = 1025
    mail_from: str = "noreply@fsp-hiring.local"

    # FSP ID (OIDC). Без FSP_ID_ISSUER — встроенный мок {PUBLIC_BASE_URL}/mock/fsp (только при включённых моках)
    fsp_id_issuer: str | None = None
    fsp_id_client_id: str = "fsp-hiring"
    fsp_id_client_secret: str = "dev-client-secret"
    fsp_api_url: str | None = None  # API достижений ФСП; без значения — API встроенного мока
    # Серверные вызовы к FSP ID и API идут на этот origin вместо публичного (в compose — http://api:8000)
    fsp_server_base: str | None = None
    # DaData (проверка ИНН для уровня L2). Без DADATA_URL — встроенный мок {PUBLIC_BASE_URL}/mock/dadata (только при моках)
    dadata_url: str | None = None
    dadata_token: SecretStr | None = None
    mocks_enabled: bool | None = None  # встроенные моки внешних систем; по умолчанию — как DEMO_MODE

    @property
    def mocks_on(self) -> bool:
        return self.demo_mode if self.mocks_enabled is None else self.mocks_enabled

    @property
    def fsp_issuer(self) -> str:
        return self.fsp_id_issuer or f"{self.public_base_url.rstrip('/')}/mock/fsp/realms/fsp"

    @property
    def fsp_achievements_url(self) -> str:
        return self.fsp_api_url or f"{self.public_base_url.rstrip('/')}/mock/fsp/api/v1"

    @property
    def fsp_redirect_uri(self) -> str:
        return f"{self.public_base_url.rstrip('/')}/api/v1/auth/fsp/callback"


@lru_cache
def get_settings() -> Settings:
    return Settings()


DEFAULT_SECRETS = frozenset({"", "change-me", "dev-secret-change-me"})


def validate_secrets() -> None:
    """В боевом режиме (DEMO_MODE выключен) SECRET_KEY не должен оставаться значением по умолчанию.

    Секрет задаёт HMAC выбора заданий: со значением по умолчанию кандидат может воспроизвести свои задания и ключи.
    """
    s = get_settings()
    if not s.demo_mode and s.secret_key in DEFAULT_SECRETS:
        raise RuntimeError("SECRET_KEY не задан: сгенерируйте значение и положите его в .env")
