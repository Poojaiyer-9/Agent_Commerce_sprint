from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    razorpay_key_id: str
    razorpay_key_secret: str

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"

    audit_db_path: str = "./audit_trail.db"

    policy_max_single_item_price_paise: int = 500_000
    policy_max_cart_value_paise: int = 1_000_000
    policy_max_retry_attempts: int = 2
    policy_rate_limit_actions: int = 5
    policy_rate_limit_window_seconds: int = 60

    frontend_origin: str = "http://localhost:5173"


settings = Settings()
