"""Central configuration loaded from environment variables / `.env`.

Every service (API, CV worker, geo worker) reads the same settings object so
that connection strings, storage layout and thresholds stay consistent.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- General ---
    app_env: str = "development"
    app_name: str = "WSS Map Processing Platform"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"

    # --- Database ---
    database_url: str = "postgresql+psycopg://wss:wss@localhost:5432/wss"
    db_echo: bool = False

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Object storage ---
    s3_endpoint: str = "http://localhost:3900"
    s3_region: str = "garage"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "wss"
    s3_force_path_style: bool = True
    s3_presign_expire: int = 900
    # Endpoint the BROWSER uses. Presigned URLs are signed against this host,
    # so it must be reachable from the browser (may differ from the internal
    # endpoint when a reverse proxy / NAT sits in between).
    s3_public_endpoint: str = ""
    # Optional file-based credentials (Docker secrets pattern); used when the
    # corresponding env value is empty.
    s3_access_key_file: str = ""
    s3_secret_key_file: str = ""

    # --- Auth ---
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 720

    # --- Bootstrap ---
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str = "admin123"
    bootstrap_admin_name: str = "Administrator"
    # When true, an existing bootstrap admin's password is reset to
    # `bootstrap_admin_password` on startup. Recovery path for a lost/changed
    # admin password when there is no database access; keep false normally.
    bootstrap_admin_force_reset: bool = False

    # --- Upload validation ---
    upload_max_bytes: int = 52_428_800
    upload_allowed_types: str = "image/jpeg,image/png,image/webp,image/tiff"

    # --- OCR ---
    ocr_engine: str = "tesseract"
    ocr_lang: str = "eng"
    ocr_psm: int = 7
    ocr_whitelist: str = "0123456789OolISsBZG"

    # --- IDSUBSLS ---
    id_pattern: str = r"^\d{16}$"
    id_length: int = 16

    # --- Thresholds ---
    paper_min_confidence: float = 0.60
    ocr_auto_accept_confidence: float = 0.90
    ocr_review_confidence: float = 0.55
    fuzzy_auto_accept_ratio: float = 0.93
    fuzzy_review_ratio: float = 0.72
    quality_min_score: float = 0.50

    # --- Upscaling ---
    upscale_min_short_side: int = 1600
    upscale_max_factor: float = 2.0

    # --- Worker ---
    worker_concurrency: int = 1
    job_max_attempts: int = 3
    job_visibility_timeout: int = 1800
    worker_tmp_dir: str = "/tmp/wss"

    # --- Frontend ---
    next_public_api_base_url: str = "http://localhost:8000"
    api_internal_url: str = "http://api:8000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_upload_types(self) -> list[str]:
        return [t.strip() for t in self.upload_allowed_types.split(",") if t.strip()]

    @staticmethod
    def _read_secret_file(path: str) -> str:
        if not path:
            return ""
        try:
            with open(path, encoding="utf-8") as handle:
                return handle.read().strip()
        except OSError:
            return ""

    @property
    def resolved_s3_access_key(self) -> str:
        return self.s3_access_key or self._read_secret_file(self.s3_access_key_file)

    @property
    def resolved_s3_secret_key(self) -> str:
        return self.s3_secret_key or self._read_secret_file(self.s3_secret_key_file)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
