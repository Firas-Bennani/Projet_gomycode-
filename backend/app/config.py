from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Industrial Copilot"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"
    
    # Server
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"
    
    # Database
    DATABASE_URL: str = "sqlite:///./copilot.db"
    
    # Redis / MQTT
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    MQTT_BROKER: str = "localhost"
    MQTT_PORT: int = 1883
    
    # AI / LLM
    LLM_PROVIDER: str = "simulated"  # or openai, gemini, ollama
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
