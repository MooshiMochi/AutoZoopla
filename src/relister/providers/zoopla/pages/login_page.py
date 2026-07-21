"""Zoopla login page helpers."""

import asyncio
import logging

from playwright.async_api import Page, TimeoutError as PWTimeoutError

from relister.providers.zoopla import selectors

logger = logging.getLogger(__name__)


class ZooplaLoginPage:
    LOGIN_URL = selectors.LOGIN_URL
    DASHBOARD_URL = selectors.DASHBOARD_URL
    CHECK_LOGIN_URL = selectors.CHECK_LOGIN_URL

    def __init__(self, page: Page, provider) -> None:
        self.page: Page = page
        self.provider = provider

    async def login(
        self,
    ) -> None:

        await self.page.locator("input#username").fill(self.provider.account.username)
        await self.page.locator("input#password").fill(self.provider.account.password)

        await self.page.get_by_role(
            "button",
            name="Sign in",
        ).click()

        await self._handle_auth_code_prompt_if_needed()

        await self.page.wait_for_url("**/pro.zoopla.co.uk/**")

        await self.provider.detect_and_close_cookie_prompt(self.page)

        logger.info("Login completed")

    async def _handle_auth_code_prompt_if_needed(self) -> None:
        # Check if the auth code prompt is present
        auth_code_input = self.page.locator("input#code")
        try:
            await auth_code_input.wait_for(
                state="visible",
                timeout=1_000,
            )
            logger.info("Auth code prompt detected.")
        except PWTimeoutError:
            logger.debug("No auth code prompt detected.")
            return

        # Prompt the user for the auth code
        auth_code = await asyncio.to_thread(
            input,
            "Enter the authentication code: ",
        )

        # Fill in the auth code and submit
        await auth_code_input.fill(auth_code)
        await self.page.wait_for_timeout(
            200
        )  # Wait for 0.2 seconds before clicking the continue button
        await self.page.get_by_role(
            "button",
            name="Continue",
        ).click()
