from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    CLERK_SIGNING_SECRET:str
    ENV: str = "development"
    CLIENT_URL: str = "http://localhost:3000"

    class Config:
        env_file = ".env"

settings = Settings()
