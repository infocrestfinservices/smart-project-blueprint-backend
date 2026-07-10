from dotenv import load_dotenv
load_dotenv()

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    DEEPSEEK_API_KEY: str = "sk-e8bda1699430447e97c0d6fcbe83471a"


    DEEPSEEK_MODEL: str = "deepseek-v4-flash"
    SECRET_KEY: str = "changeme"
    RESEND_API_KEY: str = ""
    FROM_EMAIL: str = "onboarding@resend.dev"
    FROM_NAME: str = "Smart Project Blueprint"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    class Config:
        env_file = ".env"

settings = Settings()