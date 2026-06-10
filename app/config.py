from functools import lru_cache
from os import getenv

from dotenv import load_dotenv


load_dotenv()


class SettingsError(RuntimeError):
    pass


class Settings:
    def __init__(self) -> None:
        self.database_url = self._normalize_database_url(self._required("DATABASE_URL"))
        self.supabase_url = self._required("SUPABASE_URL")
        self.supabase_storage_key = (
            getenv("SUPABASE_SERVICE_ROLE_KEY")
            or getenv("SUPABASE_KEY")
            or self._raise_missing("SUPABASE_SERVICE_ROLE_KEY")
        )
        self.supabase_storage_bucket = getenv("SUPABASE_STORAGE_BUCKET", "cvs")
        self.admin_api_key = getenv("ADMIN_API_KEY", "")
        self.max_cv_upload_bytes = int(getenv("MAX_CV_UPLOAD_BYTES", str(10 * 1024 * 1024)))

    @staticmethod
    def _required(name: str) -> str:
        value = getenv(name)
        if not value:
            raise SettingsError(f"{name} is not configured")
        return value

    @staticmethod
    def _raise_missing(name: str) -> str:
        raise SettingsError(f"{name} is not configured")

    @staticmethod
    def _normalize_database_url(value: str) -> str:
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
