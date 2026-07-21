import asyncio
import logging
from collections.abc import Awaitable, Callable
from urllib.parse import urlparse
from weakref import WeakKeyDictionary

from playwright.async_api import (
    BrowserContext,
    Frame,
    Page,
)
from playwright._impl._errors import TargetClosedError

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
        self._login_task: asyncio.Task[None] | None = None

        self._started = False
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
            return
        else:
            self._start_login_task(page)

    def _start_login_task(self, page: Page) -> None:
        if self._login_task and not self._login_task.done():
            return

        self._login_task = asyncio.create_task(
            self._handle_login(page), name="ContextLoginGuard._handle_login"
        )

    async def _handle_login(self, page: Page) -> None:
        # Redirect chains may produce several navigation events.
        if self._login_lock.locked():
            return

        async with self._login_lock:
            # Recheck after acquiring the lock.
            if not self.provider.is_login_url(page.url):
                return

            await self.provider.login(page)
            if self.save_session_callback:
                await self.save_session_callback(self.ctx)
                logger.debug("Saved session state after login.")

    async def wait_until_ready(self, page: Page) -> None:
        """Wait for the current authentication flow to complete

        Args:
            page (Page): The Playwright page to wait for.
        """
        if self.provider.is_login_url(page.url):
            self._start_login_task(page)

        while True:
            task = self._login_task

            if task is None:
                return

            await asyncio.shield(task)

            if task is self._login_task:
                return
