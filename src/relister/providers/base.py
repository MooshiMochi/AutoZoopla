# src/relister/providers/base.py

from abc import ABC, abstractmethod
from pathlib import Path

from playwright.async_api import BrowserContext, Page
from pydantic.v1 import HttpUrl

from relister.domain.accounts import ProviderAccount
from relister.domain.models import PropertyListing


class PropertyProvider(ABC):
    name: str
    account: ProviderAccount

    @abstractmethod
    def is_login_url(self, url: str | HttpUrl) -> bool:
        pass

    @abstractmethod
    async def detect_and_close_cookie_prompt(self, page: Page) -> None:
        pass

    @abstractmethod
    async def login(
        self,
        page: Page,
    ) -> None:
        pass

    @abstractmethod
    async def delete_listing(
        self,
        context: BrowserContext,
        listing_url: str,
        submit: bool = True,
    ) -> bool:
        pass

    @abstractmethod
    async def scrape_listing(
        self,
        context: BrowserContext,
        listing_url: str,
    ) -> PropertyListing:
        pass

    @abstractmethod
    async def create_listing(
        self,
        context: BrowserContext,
        listing: PropertyListing,
        images_path: Path | None = None,
        *,
        submit: bool,
    ) -> tuple[str, str] | None:
        pass

    @abstractmethod
    async def listing_exists(
        self,
        context: BrowserContext,
        reference: str,
    ) -> bool:
        pass
