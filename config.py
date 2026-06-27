from dotenv import load_dotenv
load_dotenv()

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    CLAUDE_API_KEY: str = ""
    SECRET_KEY: str = "changeme"

    class Config:
        env_file = ".env"

settings = Settings()