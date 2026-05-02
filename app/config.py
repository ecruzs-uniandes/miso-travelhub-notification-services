from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENV: str = "local"
    LOG_LEVEL: str = "INFO"
    PORT: int = 8004

    DATABASE_URL: str = "postgresql+asyncpg://travelhub_app:localpass@localhost:5432/travelhub_notifications?ssl=disable"
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10

    KAFKA_CONSUMER_ENABLED: bool = False
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_CONSUMER_GROUP: str = "notification-services-group"
    KAFKA_DLQ_TOPIC: str = "notification-dlq"

    JWT_ISSUER: str = "https://auth.travelhub.app"
    JWT_AUDIENCE: str = "travelhub-api"

    INTERNAL_NOTIFY_TOKEN: str = "change-me"

    SENDGRID_API_KEY: str = ""
    SENDGRID_FROM_EMAIL: str = "noreply@travelhub.app"
    SENDGRID_FROM_NAME: str = "TravelHub"
    SENDGRID_SANDBOX: bool = True

    FCM_CREDENTIALS_JSON: str = ""
    FCM_PROJECT_ID: str = ""

    APP_URL: str = "https://app.travelhub.app"
    SUPPORT_EMAIL: str = "soporte@travelhub.app"

    RETRY_MAX_ATTEMPTS: int = 3
    RETRY_BACKOFF_BASE: int = 2
    CB_FAILURE_THRESHOLD: int = 5
    CB_RECOVERY_TIMEOUT: int = 30


settings = Settings()
