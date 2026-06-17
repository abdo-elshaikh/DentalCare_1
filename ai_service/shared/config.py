"""Centralized configuration using Pydantic for both API and UI."""

import os
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings from environment or defaults."""
    
    # Model & inference
    model_path: str = Field(default="models/best_model.pth", env="MODEL_PATH")
    input_size: int = Field(default=768, env="INPUT_SIZE")
    num_landmarks: int = Field(default=19, env="NUM_LANDMARKS")
    
    # API URLs
    api_url: str = Field(default="http://localhost:8000", env="CEPHALO_API_URL")
    ui_url: str = Field(default="http://localhost:8501", env="CEPHALO_UI_URL")
    
    # LLM providers
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", env="OPENAI_MODEL")
    gemini_api_key: str = Field(default="", env="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-1.5-pro", env="GEMINI_MODEL")
    
    # Clinical thresholds
    min_landmark_confidence: float = Field(default=0.50, env="MIN_LANDMARK_CONFIDENCE")
    require_calibration: bool = Field(default=True, env="REQUIRE_CALIBRATION")
    
    # Database
    db_path: str = Field(default="data/cases.sqlite3", env="DB_PATH")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        
    @property
    def api_url_clean(self) -> str:
        """API URL without trailing slash."""
        return self.api_url.rstrip("/")


settings = Settings()
