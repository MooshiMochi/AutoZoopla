from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from relister.providers.factory import get_provider
from relister.workflows.relist_listing import relist_property

from .prompt_bridge import (
    PromptBridge,
    PromptCancelledError,
    redirect_console_prompts,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RelistRequest:
    source: str
    destination: str
    listing_url: str
    images_path: Path | None
    publish: bool
    headless: bool


class RelistWorker(QObject):
    """
    Run the Playwright workflow outside the Qt main thread.

    asyncio.run() creates an event loop owned by this QThread. This keeps the
    Qt interface responsive, but blocking functions must still be moved off
    the Playwright event loop using asyncio.to_thread().
    """

    succeeded = Signal(object)
    failed = Signal(str)
    cancelled = Signal()
    done = Signal()
    status_changed = Signal(str)

    def __init__(
        self,
        request: RelistRequest,
        prompt_bridge: PromptBridge,
    ) -> None:
        super().__init__()

        self._request = request
        self._prompt_bridge = prompt_bridge

        self._cancel_requested = threading.Event()

        self._loop: asyncio.AbstractEventLoop | None = None
        self._async_task: asyncio.Task[Any] | None = None

    @Slot()
    def run(self) -> None:
        self._prompt_bridge.reset()
        self.status_changed.emit("Starting relist workflow...")

        try:
            # This compatibility wrapper means existing calls such as:
            #
            # await asyncio.to_thread(
            #     input,
            #     "Enter verification code: ",
            # )
            #
            # are displayed in the Qt User input panel.
            with redirect_console_prompts(self._prompt_bridge):
                result = asyncio.run(self._execute())

        except (asyncio.CancelledError, PromptCancelledError):
            logger.warning("Relist process cancelled.")
            self.cancelled.emit()

        except Exception as exc:
            logger.exception("Relist process failed")
            self.failed.emit(str(exc) or exc.__class__.__name__)

        else:
            self.succeeded.emit(result)

        finally:
            self._loop = None
            self._async_task = None
            self.done.emit()

    async def _execute(self):
        self._loop = asyncio.get_running_loop()
        self._async_task = asyncio.current_task()

        if self._cancel_requested.is_set():
            raise asyncio.CancelledError

        self.status_changed.emit("Loading providers...")

        source_provider = get_provider(self._request.source)

        destination_provider = get_provider(
            self._request.destination,
            destination=True,
        )

        self.status_changed.emit("Browser automation is running...")

        result = await relist_property(
            source_provider=source_provider,
            destination_provider=destination_provider,
            listing_url=self._request.listing_url,
            images_path=self._request.images_path,
            dry_run=not self._request.publish,
            headless=self._request.headless,
        )

        if self._cancel_requested.is_set():
            raise asyncio.CancelledError

        return result

    def request_cancel(self) -> None:
        """
        Request cancellation safely from the Qt main thread.

        Cancelling the asyncio task alone cannot terminate an executor thread
        waiting inside asyncio.to_thread(). Cancelling the prompt bridge also
        wakes that thread so asyncio.run() can shut down cleanly.
        """

        self._cancel_requested.set()
        self._prompt_bridge.cancel()

        loop = self._loop
        task = self._async_task

        if loop is not None and task is not None and not task.done():
            loop.call_soon_threadsafe(task.cancel)
