from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+asyncpg://monitor:monitor@postgres:5432/monitor"
    prometheus_url: str = "http://prometheus:9090"
    service_urls: dict[str, str] = {"demo-service": "http://demo-service:8001"}
    admin_username: str = "admin"
    admin_password_hash: str
    session_secret: str = Field(min_length=32)
    ingest_token: str = Field(min_length=32)
    demo_control_token: str = Field(min_length=32)
    cookie_secure: bool = False
    public_origin: str = "http://localhost:8080"
    session_seconds: int = Field(default=3600, ge=60)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    detection_interval: float = Field(default=5, ge=1)
    startup_grace: float = Field(default=30, ge=0)
    error_threshold: float = Field(default=10, ge=0, le=100)
    latency_threshold: float = Field(default=1, gt=0)
    min_requests: int = Field(default=20, ge=1)
    unavailable_seconds: float = Field(default=20, ge=0)
    error_log_threshold: int = Field(default=5, ge=1)
    cpu_threshold: float = Field(default=80, gt=0)
    memory_threshold: float = Field(default=256, gt=0)
    resource_seconds: float = Field(default=30, ge=0)
    enable_detection: bool = True

    @model_validator(mode="after")
    def valid_deployment(self):
        if self.public_origin.startswith("https://") and not self.cookie_secure:
            raise ValueError("HTTPS deployments require COOKIE_SECURE=true")
        if not self.cookie_secure and self.public_origin not in {
            "http://localhost:8080",
            "http://127.0.0.1:8080",
        }:
            raise ValueError("Non-local deployments require HTTPS and secure cookies")
        if self.cookie_secure and not self.public_origin.startswith("https://"):
            raise ValueError("Secure deployments require an HTTPS PUBLIC_ORIGIN")
        if not self.service_urls:
            raise ValueError("At least one monitored service is required")
        if not self.admin_password_hash.startswith("pbkdf2_sha256$"):
            raise ValueError("Run scripts/configure.py to generate the admin password hash")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
