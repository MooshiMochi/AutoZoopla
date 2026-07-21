# src/relister/browser/session.py

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from playwright.async_api import BrowserContext, async_playwright

from relister.browser.login_guard import ContextLoginGuard
from relister.providers.base import PropertyProvider


class BrowserSession:
    def __init__(
        self,
        provider: PropertyProvider,
        *,
        headless: bool = False,
    ) -> None:
        self.provider = provider
        self.headless = headless
        self.login_gate: ContextLoginGuard | None = None

        session_name = f"{provider.name}-{provider.account.alias}.json"

        self.state_path = Path("data/browser_states") / session_name

    async def _save_session_state(self, context: BrowserContext) -> None:
        if not self.state_path.parent.exists():
            self.state_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

        await context.storage_state(
            path=str(self.state_path),
        )

    @asynccontextmanager
    async def authenticated_context(
        self,
    ) -> AsyncIterator[BrowserContext]:
        self.state_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        async with async_playwright() as playwright:
            browser = await playwright.firefox.launch(
                headless=self.headless,
            )

            context_options = {}

            if self.state_path.exists():
                context_options["storage_state"] = str(self.state_path)

            context = await browser.new_context(
                **context_options,
            )

            self.login_gate = ContextLoginGuard(
                self.provider, context, save_session_callback=self._save_session_state
            )
            self.login_gate.start()

            try:
                yield context
            finally:
                if self.login_gate:
                    await self.login_gate.close()

                await context.close()
                await browser.close()
