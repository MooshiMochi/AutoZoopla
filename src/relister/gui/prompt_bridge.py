from __future__ import annotations

import asyncio
import builtins
import getpass
import threading
from contextlib import contextmanager
from typing import Iterator, Protocol

from PySide6.QtCore import QObject, Signal


class PromptCancelledError(RuntimeError):
    """Raised when the current GUI operation is cancelled during a prompt."""


class UserInteraction(Protocol):
    """Interface used by providers and workflows to request user input."""

    async def ask(
        self,
        message: str,
        *,
        sensitive: bool = False,
    ) -> str:
        """Ask the user for a value without blocking the asyncio event loop."""
        ...


class PromptBridge(QObject):
    """
    Thread-safe bridge between Playwright's asyncio workflow and the Qt UI.

    ask_blocking() waits on a condition variable and must never be called
    directly from the Playwright event-loop thread.

    ask() is the preferred async API. It moves the blocking wait into an
    executor thread using asyncio.to_thread(), leaving Playwright's event
    loop free to process browser events, timers and network messages.

    The redirect_console_prompts() compatibility layer also supports existing
    code that already uses:

        code = await asyncio.to_thread(
            input,
            "Enter verification code: ",
        )
    """

    prompt_requested = Signal(str, bool)
    prompt_finished = Signal()

    def __init__(self) -> None:
        super().__init__()

        self._condition = threading.Condition()
        self._response: str | None = None
        self._waiting = False
        self._cancelled = False

    @property
    def is_waiting(self) -> bool:
        with self._condition:
            return self._waiting

    def reset(self) -> None:
        """Prepare the bridge for a new workflow run."""

        with self._condition:
            self._response = None
            self._waiting = False
            self._cancelled = False
            self._condition.notify_all()

    async def ask(
        self,
        message: str,
        *,
        sensitive: bool = False,
    ) -> str:
        """
        Request input without blocking the caller's asyncio event loop.

        This is the preferred method for newly written provider code.
        """

        return await asyncio.to_thread(
            self.ask_blocking,
            message,
            sensitive=sensitive,
        )

    async def ask_password(
        self,
        message: str = "Password: ",
    ) -> str:
        """Convenience wrapper for a masked input prompt."""

        return await self.ask(
            message,
            sensitive=True,
        )

    def ask_blocking(
        self,
        message: str = "",
        *,
        sensitive: bool = False,
    ) -> str:
        """
        Request input and block the current thread until the user responds.

        Call this only from a background or executor thread. Async code should
        use await ask(...) instead.
        """

        with self._condition:
            if self._cancelled:
                raise PromptCancelledError("The operation was cancelled.")

            if self._waiting:
                raise RuntimeError(
                    "A second prompt was requested before the first completed."
                )

            self._waiting = True
            self._response = None

        self.prompt_requested.emit(
            message or "Input required:",
            sensitive,
        )

        try:
            with self._condition:
                while self._response is None and not self._cancelled:
                    self._condition.wait()

                if self._cancelled:
                    raise PromptCancelledError("The operation was cancelled.")

                response = self._response
                self._response = None

                return response or ""
        finally:
            with self._condition:
                self._waiting = False

            self.prompt_finished.emit()

    def submit_response(self, response: str) -> None:
        """Supply the value entered in the Qt input panel."""

        with self._condition:
            if not self._waiting or self._cancelled:
                return

            self._response = response
            self._condition.notify_all()

    def cancel(self) -> None:
        """
        Cancel the active prompt and wake its executor thread.

        Cancelling a coroutine awaiting asyncio.to_thread() does not forcibly
        terminate the underlying executor function, so the waiting condition
        must also be released.
        """

        with self._condition:
            self._cancelled = True
            self._condition.notify_all()


@contextmanager
def redirect_console_prompts(
    prompt_bridge: PromptBridge,
) -> Iterator[None]:
    """
    Redirect input() and getpass.getpass() to the Qt input panel.

    Existing provider code should still invoke these blocking functions through
    asyncio.to_thread():

        code = await asyncio.to_thread(
            input,
            "Enter verification code: ",
        )

    Calling input() directly inside an async function would still block the
    Playwright event loop, even though the workflow runs in a QThread.
    """

    original_input = builtins.input
    original_getpass = getpass.getpass

    def gui_input(prompt: str = "") -> str:
        return prompt_bridge.ask_blocking(
            str(prompt),
            sensitive=False,
        )

    def gui_getpass(
        prompt: str = "Password: ",
        stream=None,
    ) -> str:
        del stream

        return prompt_bridge.ask_blocking(
            str(prompt),
            sensitive=True,
        )

    builtins.input = gui_input
    getpass.getpass = gui_getpass

    try:
        yield
    finally:
        builtins.input = original_input
        getpass.getpass = original_getpass
