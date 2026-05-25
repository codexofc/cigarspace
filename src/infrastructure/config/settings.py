# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Application settings loaded from environment variables / .env file."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class _Base(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


class PostgresSettings(_Base):
    model_config = SettingsConfigDict(env_prefix="POSTGRES_", env_file=".env", extra="ignore")

    user: str = "cigars"
    password: str = "cigars"
    db: str = "cigars"
    host: str = "localhost"
    port: int = 5432

    @computed_field  # type: ignore[prop-decorator]
    @property
    def dsn(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"


class RedisSettings(_Base):
    model_config = SettingsConfigDict(env_prefix="REDIS_", env_file=".env", extra="ignore")

    host: str = "localhost"
    port: int = 6379
    db: int = 0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def dsn(self) -> str:
        return f"redis://{self.host}:{self.port}/{self.db}"


class AppSettings(_Base):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    env: Literal["dev", "test", "prod"] = "dev"


class LogSettings(_Base):
    model_config = SettingsConfigDict(env_prefix="LOG_", env_file=".env", extra="ignore")

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    format: Literal["console", "json"] = "console"


class S3Settings(_Base):
    """S3-compatible object storage settings (SeaweedFS, MinIO, AWS S3, R2…)."""

    model_config = SettingsConfigDict(env_prefix="S3_", env_file=".env", extra="ignore")

    endpoint_url: str = "http://localhost:8333"
    region: str = "us-east-1"
    bucket: str = "cigars-media"
    access_key_id: str = "cigars-dev"
    secret_access_key: str = "cigars-dev-secret"


class MediaSettings(_Base):
    """Media pipeline settings (validation, conversion)."""

    model_config = SettingsConfigDict(env_prefix="MEDIA_", env_file=".env", extra="ignore")

    max_bytes: int = 8 * 1024 * 1024  # 8 MiB
    webp_quality: int = 85  # 0..100


class PisteSettings(_Base):
    """DILA API access via the PISTE OAuth2 platform (api.piste.gouv.fr)."""

    model_config = SettingsConfigDict(env_prefix="PISTE_", env_file=".env", extra="ignore")

    client_id: str = ""
    client_secret: str = ""
    oauth_url: str = "https://oauth.piste.gouv.fr/api/oauth/token"
    api_base_url: str = "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app"
    scope: str = "openid"


class ApiSettings(_Base):
    """Public HTTP API settings."""

    model_config = SettingsConfigDict(env_prefix="API_", env_file=".env", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 2

    # CORS — defaults are permissive for dev; fail-loud in prod when ["*"].
    cors_origins: list[str] = ["*"]

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_seconds: int = 15 * 60  # 15 min
    refresh_token_expire_seconds: int = 7 * 24 * 60 * 60  # 7 d

    # Rate-limiting (slowapi format, Redis backend).
    rate_limit_default: str = "60/minute"

    # If True, the embedder model is loaded eagerly in lifespan so the first
    # /cigars/search call doesn't pay the cold-start cost. Adds ~420 MB RAM.
    warm_embedder_on_startup: bool = False

    # OpenAPI / Swagger UI / ReDoc exposure (turn off in some prod configs).
    docs_enabled: bool = True

    # Hard caps for pagination (applied even if the client asks higher).
    max_page_size: int = 100
    max_offset: int = 10_000


class Settings:
    def __init__(self) -> None:
        self.app = AppSettings()
        self.postgres = PostgresSettings()
        self.redis = RedisSettings()
        self.log = LogSettings()
        self.s3 = S3Settings()
        self.media = MediaSettings()
        self.piste = PisteSettings()
        self.api = ApiSettings()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
