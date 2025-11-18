from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET: str
    JWT_ALGO: str = "HS256"

    class Config:
        env_file = ".env"

settings = Settings()
