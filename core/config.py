from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    APP_NAME: str = "IoT Backend"
    DEBUG: bool = False
    SECRET_KEY: str = Field(default="change-me")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    DATABASE_URL: str = Field(default="sqlite:///./iot.db")

    MQTT_BROKER: str = Field(default="localhost")
    MQTT_PORT: int = Field(default=1883)
    MQTT_USER: str = Field(default="")
    MQTT_PASS: str = Field(default="")
    MQTT_CLIENT_ID: str = Field(default="fastapi-backend")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()