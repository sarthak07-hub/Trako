import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "TRAKO - Smart Bus Transportation Platform"
    TAGLINE: str = "Smarter Journeys. Better Connections."
    API_V1_PREFIX: str = "/api/v1"
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./trako.db")
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "trako-super-secure-production-ready-jwt-secret-key-2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    
    # Trip & Boarding Rules
    BOARDING_DEADLINE_MINUTES: int = 10  # minutes after scheduled stop time to declare no-show
    
    # GPS Tracking
    GPS_STALE_THRESHOLD_SECONDS: int = 120  # mark UNAVAILABLE if no update in 2 mins
    GPS_DELAY_THRESHOLD_MINUTES: int = 15   # mark DELAYED if behind schedule
    
    # Web & Hosting
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    BASE_URL: str = os.getenv("BASE_URL", "http://localhost:8000")
    CORS_ORIGINS: List[str] = ["*"]

settings = Settings()
