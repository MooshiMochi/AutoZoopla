# src/relister/core/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    zoopla_source_username: str = ""
    zoopla_source_password: str = ""

    zoopla_destination_username: str = ""
    zoopla_destination_password: str = ""

    onthemarket_source_username: str = ""
    onthemarket_source_password: str = ""

    onthemarket_destination_username: str = ""
    onthemarket_destination_password: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
