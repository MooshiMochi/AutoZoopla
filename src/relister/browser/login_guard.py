import asyncio
import logging
from collections.abc import Awaitable, Callable
from urllib.parse import urlparse
from weakref import WeakKeyDictionary

from playwright.async_api import (
    BrowserContext,
    Frame,
    Page,
    TimeoutError as PWTimeoutError,
    Error as PlaywrightError,
)
from playwright._impl._errors import TargetClosedError

from pytest_playwright.pytest_playwright import page

from relister.providers.base import PropertyProvider

logger = logging.getLogger(__name__)


class ContextLoginGuard:
    """
    Watches a Playwright page and runs the login flow whenever the
    main page navigates to a matching login URL.
    """

    def __init__(
        self,
        provider: PropertyProvider,
        ctx: BrowserContext,
        save_session_callback: (
            Callable[[BrowserContext], Awaitable[None]] | None
        ) = None,
    ) -> None:
        self.ctx = ctx
        self.provider = provider
        self.save_session_callback = save_session_callback

        # Prevent multiple navigation events from starting login concurrently.
        self._login_lock = asyncio.Lock()
        self._started = False
        self._return_urls: WeakKeyDictionary[Page, str] = WeakKeyDictionary()
        self._cookie_prompt_tasks: WeakKeyDictionary[Page, asyncio.Task[None]] = (
            WeakKeyDictionary()
        )

    def start(self) -> None:
        self.ctx.on("framenavigated", self._on_frame_navigated)

    async def close(self):
        logger.debug("Closing ContextLoginGuard and cancelling cookie prompt tasks.")
        tasks = [task for task in self._cookie_prompt_tasks.values() if not task.done()]
        for task in tasks:
            task.cancel()

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self._cookie_prompt_tasks.clear()

    def _start_cookie_watcher(self, page: Page) -> None:
        existing_task = self._cookie_prompt_tasks.get(page)
        if existing_task and not existing_task.done():
            existing_task.cancel()

        task = asyncio.create_task(self.provider.detect_and_close_cookie_prompt(page))
        self._cookie_prompt_tasks[page] = task

        def _cleanup(done_task: asyncio.Task[None]) -> None:
            self._cookie_prompt_tasks.pop(page, None)
            if done_task.cancelled():
                return
            exc = done_task.exception()
            if exc and not isinstance(exc, asyncio.CancelledError):
                if (
                    not isinstance(exc, TargetClosedError)
                    and "closed" not in str(exc).lower()
                ):
                    logger.debug(
                        "Cookie prompt watcher finished with error", exc_info=exc
                    )

        task.add_done_callback(_cleanup)

    async def _on_frame_navigated(self, frame: Frame) -> None:
        page = frame.page

        # Ignore iframe navigation.
        if frame != page.main_frame:
            return

        self._start_cookie_watcher(page)

        if not self.provider.is_login_url(frame.url):
            self._return_urls[page] = frame.url
            return

        await self._ensure_logged_in(page)

    async def _ensure_logged_in(self, page: Page) -> None:
        # Redirect chains may produce several navigation events.
        if self._login_lock.locked():
            return

        async with self._login_lock:
            # Recheck after acquiring the lock.
            if not self.provider.is_login_url(page.url):
                return

            return_url = self._return_urls.get(page)

            await self._perform_login(page)

            await self._restore_previous_page(page, return_url)
            self._return_urls.pop(page, None)

    async def _perform_login(self, page: Page) -> None:
        logger.debug(f"Login detected on: {page.url}")

        await self.provider.login(page)

        if self.save_session_callback:
            await self.save_session_callback(self.ctx)
            logger.debug("Saved session state after login.")

    async def _restore_previous_page(self, page: Page, return_url: str | None) -> None:
        try:
            history_length = await page.evaluate("() => window.history.length")
        except Exception:
            history_length = 0

        if history_length and history_length > 1:
            await page.go_back()
            await page.wait_for_load_state("networkidle")
            logger.debug("Returned to previous page after login.")
            return

        if return_url and not self.provider.is_login_url(return_url):
            await page.goto(return_url)
            await page.wait_for_load_state("networkidle")
