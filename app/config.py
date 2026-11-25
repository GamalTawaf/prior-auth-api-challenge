from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://prior:prior@localhost:5432/prior_auth"
    jwt_secret: str = "dev-only-change-me"
    jwt_algorithm: str = "HS256"
    otel_service_name: str = "prior-auth-api"


settings = Settings()
