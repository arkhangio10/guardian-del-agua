from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    sentinel_hub_client_id: str = ""
    sentinel_hub_client_secret: str = ""
    zavu_api_key: str = ""
    zavu_base_url: str = "https://api.zavu.dev/v1"
    zavu_sender: str = ""
    email_from: str = ""
    context7_api_key: str = ""
    resend_api_key: str = ""
    openrouter_api_key: str = ""
    google_cloud_project: str = ""
    google_application_credentials: str = ""
    firestore_emulator_host: str = ""
    confidence_threshold: float = 0.70

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
