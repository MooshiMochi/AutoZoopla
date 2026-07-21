# src/relister/domain/accounts.py

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderAccount:
    alias: str
    username: str
    password: str
