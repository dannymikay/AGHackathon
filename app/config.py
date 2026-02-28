from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://agrimatch:agrimatch@localhost:5432/agrimatch"

    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Stripe Connect — escrow and transfer payments
    STRIPE_SECRET_KEY: str = "sk_test_placeholder"
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_RESTRICTED_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = "whsec_placeholder"

    # Google Cloud Vision API — AI crop photo grading
    # Falls back to OpenCV pipeline when not set.
    GOOGLE_CLOUD_VISION_API_KEY: str = ""

    # OpenRouteService — real driving routes and ETAs for logistics matching
    # Falls back to straight-line distance estimates when not set.
    OPENROUTESERVICE_API_KEY: str = ""

    # Firebase Cloud Messaging — push notifications for mobile/web clients
    # Requires firebase-credentials.json in project root for full FCM push.
    # WebSocket notifications always work without this.
    FCM_PROJECT_NUMBER: str = ""

    POSTGIS_ENABLED: bool = True
    DEMO_MODE: bool = False

    APP_ENV: str = "development"

    @model_validator(mode="after")
    def check_production_secrets(self) -> "Settings":
        """Fail fast in non-development environments when placeholder secrets are still set."""
        if self.APP_ENV != "development":
            if self.SECRET_KEY == "dev-secret-key-change-in-production":
                raise ValueError(
                    "SECRET_KEY must be changed from its default value in non-development environments"
                )
            if self.STRIPE_SECRET_KEY == "sk_test_placeholder":
                raise ValueError(
                    "STRIPE_SECRET_KEY must be set in non-development environments"
                )
        return self


settings = Settings()
