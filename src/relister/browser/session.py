# src/relister/browser/session.py

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from playwright.async_api import BrowserContext, async_playwright

from relister.browser.login_guard import ContextLoginGuard
from relister.core import paths
from relister.core.security import get_cipher, hash_name
from relister.providers.base import PropertyProvider

logger = logging.getLogger(__name__)


def session_filename(provider_name: str, alias: str) -> str:
    """Opaque, non-correlatable filename for a provider account's session."""

    return hash_name(provider_name, alias) + ".enc"


def save_state(path: Path, state: dict) -> None:
    """Encrypt and write a Playwright storage-state dict to ``path``."""

    blob = get_cipher().encrypt(json.dumps(state).encode("utf-8"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob)


def load_state(path: Path) -> dict | None:
    """Decrypt a stored session; ``None`` if missing or undecryptable."""

    if not path.exists():
        return None
    try:
        raw = get_cipher().decrypt(path.read_bytes())
    except Exception:
        logger.warning("Stored session could not be decrypted; ignoring it.")
        return None
    return json.loads(raw.decode("utf-8"))


async def _launch_browser(playwright, *, headless: bool):
    """Launch Firefox if available, otherwise fall back to WebKit."""

    try:
        return await playwright.firefox.launch(headless=headless)
    except Exception as exc:
        logger.warning("Firefox unavailable (%s); falling back to WebKit.", exc)
        return await playwright.webkit.launch(headless=headless)


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

        filename = session_filename(provider.name, provider.account.alias)
        self.state_path = paths.browser_states_dir() / filename

    async def _save_session_state(self, context: BrowserContext) -> None:
        state = await context.storage_state()
        save_state(self.state_path, state)

    @asynccontextmanager
    async def authenticated_context(
        self,
    ) -> AsyncIterator[BrowserContext]:
        async with async_playwright() as playwright:
            browser = await _launch_browser(playwright, headless=self.headless)

            context_options = {}
            stored_state = load_state(self.state_path)
            if stored_state is not None:
                context_options["storage_state"] = stored_state

            context = await browser.new_context(
                **context_options,
            )

            self.login_gate = ContextLoginGuard(
                self.provider, context, save_session_callback=self._save_session_state
            )

            # monkey patch the context to include the login_gate for access in other parts of the code
            setattr(context, "login_gate", self.login_gate)
            self.login_gate.start()

            try:
                yield context
            finally:
                await self._teardown(context, browser)

    async def _teardown(self, context: BrowserContext, browser) -> None:
        """Close the guard, context and browser, always reaching the browser.

        On cancellation the CancelledError is delivered at whichever ``close``
        is awaiting. Catching it per-step (and re-raising afterwards) means a
        cancel mid-teardown can't skip ``browser.close()`` and leak the
        Firefox/WebKit process into the next relist run.
        """

        cancelled: BaseException | None = None
        closers = []
        if self.login_gate is not None:
            closers.append(("login guard", self.login_gate.close))
        closers.append(("browser context", context.close))
        closers.append(("browser", browser.close))

        for label, closer in closers:
            try:
                await closer()
            except asyncio.CancelledError as exc:  # keep tearing down, re-raise later
                cancelled = exc
            except Exception:
                logger.debug("Error closing %s during teardown.", label, exc_info=True)

        if cancelled is not None:
            raise cancelled
