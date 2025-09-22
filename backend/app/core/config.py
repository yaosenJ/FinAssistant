from pydantic import BaseModel
from typing import Optional
import os

class Settings(BaseModel):
    app_name: str = "FinAssistant Backend"
    jwt_secret: str = os.getenv("FA_JWT_SECRET", "change-me")
    jwt_algorithm: str = "HS256"
    access_token_expires_minutes: int = 60 * 24
    sqlite_url: str = os.getenv("FA_SQLITE_URL", "sqlite:///./fa.db")
    cors_origins: list[str] = [
        os.getenv("FA_FRONTEND_ORIGIN", "http://localhost:5173")
    ]

settings = Settings()