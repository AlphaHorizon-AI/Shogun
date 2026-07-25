"""Ingestion service settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class TelemetryServerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TELEMETRY_",
        env_file=".env.telemetry",
        extra="ignore",
    )

    environment: str = "development"
    database_url: str = "sqlite:///./data/telemetry.db"
    hmac_secret: str = ""
    identity_proxy_secret: str = ""
    allowed_admin_group: str = "alpha-horizon-telemetry"
    raw_event_retention_days: int = 90

    def validate_production(self) -> None:
        if self.environment == "production":
            if len(self.hmac_secret) < 32 or len(self.identity_proxy_secret) < 32:
                raise RuntimeError("Production telemetry secrets must each contain at least 32 characters")
            if not self.database_url.startswith("postgresql"):
                raise RuntimeError("Production telemetry requires PostgreSQL")


settings = TelemetryServerSettings()
