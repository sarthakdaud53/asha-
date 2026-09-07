import os
from typing import List
from pydantic import BaseModel
from dotenv import load_dotenv

# Load .env file from project root or current working dir
load_dotenv()

class Settings(BaseModel):
    APP_NAME: str = os.getenv("APP_NAME", "Digital ASHA – Rural Child Health System")
    APP_ENV: str = os.getenv("APP_ENV", "development")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8000))
    
    # Security
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY", 
        "digital_asha_super_secret_key_change_in_production_jwt_key_2026"
    )
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 1440)
    )  # 1 day default (reduce from very long defaults)
    
    # Relational Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./digital_asha.db")
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "http://localhost:5173",
    ]

settings = Settings()

# Security sanity checks (fail fast in production if secrets are not configured)
if settings.APP_ENV.lower() == "production":
    # Require a non-default SECRET_KEY in non-development environments
    default_secret_fragment = "digital_asha_super_secret_key_change_in_production"
    if default_secret_fragment in settings.SECRET_KEY:
        raise RuntimeError(
            "SECURITY: SECRET_KEY must be explicitly set in environment for production. "
            "Please set SECRET_KEY and restart the application."
        )
