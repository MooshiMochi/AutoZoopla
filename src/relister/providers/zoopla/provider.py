# src/relister/providers/zoopla/provider.py

from venv import logger

from pathlib import Path
from playwright.async_api import BrowserContext, Page, TimeoutError as PWTimeoutError
from pydantic import HttpUrl

from relister.domain.accounts import ProviderAccount
from relister.domain.models import LettingsListing, PropertyListing
from relister.providers.base import PropertyProvider
from relister.providers.zoopla.pages.listings_page import ZooplaManagedListingsPage
from relister.providers.zoopla.pages.login_page import ZooplaLoginPage
from relister.providers.zoopla.pages.listing_page import ZooplaListingPage
from relister.providers.zoopla.pages.create_listing_page import (
    ZooplaCreateListingPage,
)
from relister.providers.zoopla.selectors import MANAGED_LISTINGS_URL


class ZooplaProvider(PropertyProvider):
    name = "zoopla"

    @staticmethod
    def extract_listing_id(url: str) -> str | None:
        # Zoopla listing URLs look like
        # https://pro.zoopla.co.uk/properties/listing/5356300
        url = str(url).split("?")[0].split("#")[0].rstrip("/")
        if not url:
            return None
        return url.split("/")[-1] or None

    def __init__(self, username: str, password: str) -> None:
        self.account = ProviderAccount(
            alias=username or "zoopla",
            username=username,
            password=password,
        )

    def is_login_url(self, url: str | HttpUrl) -> bool:
        # Check if the URL matches the Zoopla login page pattern
        print("Checking if login is required for URL:", url)
        print(ZooplaLoginPage.CHECK_LOGIN_URL in str(url))
        return ZooplaLoginPage.CHECK_LOGIN_URL in str(url)

    async def detect_and_close_cookie_prompt(self, page: Page) -> None:
        deny_button = page.locator("aside#usercentrics-cmp-ui button#deny")

        for _ in range(40):  # about 10 seconds at 250ms intervals
            if await deny_button.is_visible():
                await deny_button.click()
                logger.info("Cookie prompt detected and closed.")
                return
            await page.wait_for_timeout(250)

    async def login(self, page: Page) -> None:
        """Perform login on the Zoopla website.
        Note: This method assumes that the page is already navigated to the Zoopla login page.
              This is because this page is supposed to be called from the login guard hook.

        Args:
            page (Page): the current Playwright page object to perform the login on.
        """

        await ZooplaLoginPage(page, self).login()

    async def scrape_listing(
        self,
        context: BrowserContext,
        listing_url: str,
    ) -> PropertyListing:
        page = await context.new_page()

        try:
            listing_page = ZooplaListingPage(page)
            return await listing_page.scrape(listing_url)
        finally:
            await page.close()

    async def delete_listing(
        self, context: BrowserContext, listing_url: str, submit: bool = True
    ) -> bool:
        page = await context.new_page()
        try:
            listing_page = ZooplaListingPage(page)
            return await listing_page.delete(listing_url, submit=submit)
        finally:
            await page.close()

    async def create_listing(
        self,
        context: BrowserContext,
        listing: PropertyListing,
        images_path: Path | None = None,
        *,
        submit: bool,
    ) -> tuple[str, str] | None:
        page = await context.new_page()

        try:
            create_page = ZooplaCreateListingPage(page, self)

            return await create_page.create(
                listing,
                submit=submit,
                images_path=images_path,
            )
        finally:
            if submit:
                await page.close()

    async def scrape_managed_listings(
        self, context: BrowserContext
    ) -> list[LettingsListing]:
        page = await context.new_page()

        try:
            listing_page = ZooplaManagedListingsPage(page)
            return await listing_page.scrape(MANAGED_LISTINGS_URL)
        finally:
            await page.close()

    async def listing_exists(
        self,
        context: BrowserContext,
        reference: str,
    ) -> bool:
        return False
