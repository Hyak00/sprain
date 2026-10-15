import os
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    ENVIRONMENT: Literal["development", "testing", "production"] = "development"
    DB_USER: str = "enchentes"
    DB_PASSWORD: str = "enchentes"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "enchentes"

    DB_POOL_MIN_SIZE: int = 4
    DB_POOL_MAX_SIZE: int = 20

    API_KEYS: str = ""

    @property
    def ambiente_atual(self) -> str:
        ambiente = os.getenv("ENVIRONMENT", self.ENVIRONMENT).strip().lower()
        if ambiente not in ("development", "testing", "production"):
            raise RuntimeError("ENVIRONMENT invalido.")
        return ambiente

    @property
    def chaves_validas(self) -> list[str]:
        chaves = [c.strip() for c in self.API_KEYS.split(",") if c.strip()]
        if not chaves and self.ambiente_atual == "production":
            raise RuntimeError("CRÍTICO: Variável API_KEYS não definida. Recusando inicialização do servidor em ambiente de produção.")
        return chaves

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
