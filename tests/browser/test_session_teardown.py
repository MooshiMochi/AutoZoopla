import asyncio

import pytest

from relister.browser.session import BrowserSession


class _FakeContext:
    def __init__(self, calls, *, raise_cancel=False):
        self._calls = calls
        self._raise_cancel = raise_cancel

    async def close(self):
        self._calls.append("context")
        if self._raise_cancel:
            raise asyncio.CancelledError


class _FakeBrowser:
    def __init__(self, calls):
        self._calls = calls

    async def close(self):
        self._calls.append("browser")


def test_teardown_closes_browser_and_context():
    session = BrowserSession.__new__(BrowserSession)
    session.login_gate = None
    calls: list[str] = []

    asyncio.run(session._teardown(_FakeContext(calls), _FakeBrowser(calls)))

    assert calls == ["context", "browser"]


def test_teardown_reaches_browser_when_context_close_cancelled():
    # A cancel delivered while the context is closing must not leak the browser
    # process: browser.close() still runs, and the CancelledError is re-raised.
    session = BrowserSession.__new__(BrowserSession)
    session.login_gate = None
    calls: list[str] = []

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            session._teardown(
                _FakeContext(calls, raise_cancel=True), _FakeBrowser(calls)
            )
        )

    assert calls == ["context", "browser"]
