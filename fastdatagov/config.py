from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = Field(default="development", alias="APP_ENV")
    app_secret: str = Field(default="development-only-change-me", alias="APP_SECRET")
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=5062, alias="PORT")
    base_url: str = Field(default="http://localhost:5062", alias="BASE_URL")

    repository_mode: str = Field(default="demo", alias="REPOSITORY_MODE")
    database_url: str = Field(
        default="postgresql://fastdatagov:fastdatagov@localhost:5432/fastdatagov",
        validation_alias=AliasChoices("DB_URL", "DATABASE_URL"),
        serialization_alias="DB_URL",
    )
    database_schema: str = Field(default="fast_datagov", alias="DB_SCHEMA")
    database_pool_min: int = Field(default=1,alias="DATABASE_POOL_MIN")
    database_pool_max: int = Field(default=10,alias="DATABASE_POOL_MAX")

    auth_mode: str = Field(default="dev", alias="AUTH_MODE")
    dev_auth_enabled: bool = Field(default=True, alias="DEV_AUTH_ENABLED")
    entra_tenant_id: str = Field(default="", alias="ENTRA_TENANT_ID")
    entra_client_id: str = Field(default="", alias="ENTRA_CLIENT_ID")
    entra_client_secret: str = Field(default="", alias="ENTRA_CLIENT_SECRET")
    entra_redirect_uri: str = Field(default="", alias="ENTRA_REDIRECT_URI")
    google_client_id: str = Field(default="", alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(default="", alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str = Field(default="", alias="GOOGLE_REDIRECT_URI")
    google_allowed_domains: str = Field(default="", alias="GOOGLE_ALLOWED_DOMAINS")
    google_allowed_emails: str = Field(default="", alias="GOOGLE_ALLOWED_EMAILS")
    governance_admin_emails: str = Field(default="", alias="GOVERNANCE_ADMIN_EMAILS")
    allowed_email_domains: str = Field(default="", alias="ALLOWED_EMAIL_DOMAINS")
    allowed_emails: str = Field(default="", alias="ALLOWED_EMAILS")
    allowed_hosts: str = Field(default="localhost,127.0.0.1,testserver", alias="ALLOWED_HOSTS")

    sync_interval_minutes: int = Field(default=60, alias="SYNC_INTERVAL_MINUTES")
    job_poll_seconds: int = Field(default=2, alias="JOB_POLL_SECONDS")
    job_lease_seconds: int = Field(default=900,alias="JOB_LEASE_SECONDS")
    quality_statement_timeout_seconds: int = Field(
        default=120, alias="QUALITY_STATEMENT_TIMEOUT_SECONDS"
    )
    smtp_host: str = Field(default="", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str = Field(default="", alias="SMTP_USER")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    notification_from_email: str = Field(default="fastdatagov@localhost", alias="NOTIFICATION_FROM_EMAIL")
    notification_webhook_hosts: str = Field(default="", alias="NOTIFICATION_WEBHOOK_HOSTS")
    governance_fallback_assignee: str = Field(default="governance@example.com",alias="GOVERNANCE_FALLBACK_ASSIGNEE")

    @field_validator("repository_mode")
    @classmethod
    def validate_repository_mode(cls, value: str) -> str:
        value = value.lower().strip()
        if value not in {"demo", "postgres"}:
            raise ValueError("REPOSITORY_MODE must be demo or postgres")
        return value

    @field_validator("auth_mode")
    @classmethod
    def validate_auth_mode(cls, value: str) -> str:
        value = value.lower().strip()
        if value not in {"dev", "entra", "google"}:
            raise ValueError("AUTH_MODE must be dev, entra or google")
        return value

    @field_validator("database_schema")
    @classmethod
    def validate_database_schema(cls, value: str) -> str:
        value = value.strip()
        if value != "fast_datagov":
            raise ValueError("DB_SCHEMA must be fast_datagov")
        return value

    @model_validator(mode="after")
    def validate_pool(self):
        if self.database_pool_min<0 or self.database_pool_max<1 or self.database_pool_min>self.database_pool_max:
            raise ValueError("DATABASE_POOL_MIN/MAX define an invalid pool range")
        return self

    @model_validator(mode="after")
    def validate_production_security(self):
        if self.app_env.lower() in {"production", "prod"}:
            if len(self.app_secret) < 32 or self.app_secret == "development-only-change-me":
                raise ValueError("APP_SECRET must contain at least 32 characters in production")
            identity_ready = (
                self.auth_mode == "entra" and self.entra_enabled
            ) or (
                self.auth_mode == "google" and self.google_enabled
            )
            if not identity_ready:
                raise ValueError("Production requires configured Entra ID or Google authentication")
            if not self.base_url.lower().startswith("https://"):
                raise ValueError("Production BASE_URL must use HTTPS")
            if "*" in self.host_allowlist:
                raise ValueError("Production ALLOWED_HOSTS cannot contain a wildcard")
        return self

    @property
    def entra_enabled(self) -> bool:
        return bool(
            self.entra_tenant_id
            and self.entra_client_id
            and self.entra_client_secret
        )

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def allowed_domains(self) -> set[str]:
        values = self.allowed_email_domains + "," + self.google_allowed_domains
        return {item.strip().lower() for item in values.split(",") if item.strip()}

    @property
    def allowed_users(self) -> set[str]:
        values = self.allowed_emails + "," + self.google_allowed_emails
        return {item.strip().lower() for item in values.split(",") if item.strip()}

    @property
    def governance_admins(self) -> set[str]:
        return {item.strip().lower() for item in self.governance_admin_emails.split(",") if item.strip()}

    @property
    def webhook_hosts(self) -> set[str]:
        return {item.strip().lower() for item in self.notification_webhook_hosts.split(",") if item.strip()}

    @property
    def host_allowlist(self) -> list[str]:
        return [item.strip() for item in self.allowed_hosts.split(",") if item.strip()]


@lru_cache(maxsize=1)
def settings() -> Settings:
    return Settings()
