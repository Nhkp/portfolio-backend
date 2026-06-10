from urllib.parse import quote

import httpx
from fastapi import HTTPException, status

from app.config import Settings, get_settings


class CVStorage:
    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = client or httpx.Client(
            base_url=f"{self.settings.supabase_url.rstrip('/')}/storage/v1",
            headers={
                "apikey": self.settings.supabase_storage_key,
                "Authorization": f"Bearer {self.settings.supabase_storage_key}",
            },
            timeout=30.0,
        )

    @property
    def bucket(self) -> str:
        return self.settings.supabase_storage_bucket

    def upload_pdf(self, path: str, content: bytes) -> None:
        response = self.client.post(
            self._object_path(self.bucket, path),
            content=content,
            headers={"Content-Type": "application/pdf", "x-upsert": "false"},
        )
        self._raise_for_storage_error(response)

    def download_pdf(self, bucket: str, path: str) -> bytes:
        response = self.client.get(self._object_path(bucket, path))
        self._raise_for_storage_error(response)
        return response.content

    @staticmethod
    def _object_path(bucket: str, path: str) -> str:
        encoded_path = "/".join(quote(part, safe="") for part in path.split("/"))
        return f"/object/{quote(bucket, safe='')}/{encoded_path}"

    @staticmethod
    def _raise_for_storage_error(response: httpx.Response) -> None:
        if response.is_success:
            return
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Supabase Storage error: {response.status_code}",
        )


def get_cv_storage() -> CVStorage:
    return CVStorage()
