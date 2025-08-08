import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv(override=True)

@dataclass
class Settings:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    wp_base_url: str = os.getenv("WP_BASE_URL", "").rstrip("/")
    wp_user: str = os.getenv("WP_USER", "")
    wp_app_password: str = os.getenv("WP_APP_PASSWORD", "")
    keywords_file: str = os.getenv("KEYWORDS_FILE", "./data/keywords.xlsx")
    images_dir: str = os.getenv("IMAGES_DIR", "./images")
    scheduler_enabled: bool = os.getenv("SCHEDULER_ENABLED", "false").lower() in ("1","true","yes","on")
    schedule_cron: str = os.getenv("SCHEDULE_CRON", "0 10 * * *")

settings = Settings()
