import asyncio
from types import SimpleNamespace

import pytest

from relister.providers.zoopla import selectors
from relister.providers.zoopla.pages.create_listing_page import (
    ZooplaCreateListingPage,
)


class _FakeLocator:
    def __init__(self, value):
        self.value = value
        self.fills = []

    async def input_value(self):
        return self.value

    async def fill(self, value):
        self.fills.append(value)
        self.value = value


class _FakePage:
    def __init__(self, fields):
        self._fields = fields

    def locator(self, selector):
        return self._fields[selector]


def _listing():
    return SimpleNamespace(
        address=SimpleNamespace(
            postcode="SW1A 1AA",
            house_number="10",
            street_name="Churchill",
            town="London",
        ),
        rent_pcm=1200,
    )


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    async def _instant(*_a, **_k):
        return None

    monkeypatch.setattr(
        "relister.providers.zoopla.pages.create_listing_page.asyncio.sleep",
        _instant,
    )


def test_verify_corrects_a_doubled_street_name():
    fields = {
        selectors.LISTING_ADDR_POSTCODE: _FakeLocator("SW1A 1AA"),
        selectors.LISTING_ADDR_PROPERTY_NUMBER: _FakeLocator("10"),
        selectors.LISTING_ADDR_STREET_NAME: _FakeLocator("ChurchillChurchill"),
        selectors.LISTING_ADDR_TOWN: _FakeLocator("London"),
        selectors.LISTING_PRICE_RENT: _FakeLocator("1200"),
    }
    page = ZooplaCreateListingPage(_FakePage(fields), provider=None)

    asyncio.run(page._verify_and_correct_details(_listing()))

    street = fields[selectors.LISTING_ADDR_STREET_NAME]
    assert street.value == "Churchill"
    assert street.fills == ["Churchill"]
    # Correct fields are left untouched.
    assert fields[selectors.LISTING_ADDR_TOWN].fills == []


def test_verify_leaves_correct_fields_untouched():
    fields = {
        selectors.LISTING_ADDR_POSTCODE: _FakeLocator("SW1A 1AA"),
        selectors.LISTING_ADDR_PROPERTY_NUMBER: _FakeLocator("10"),
        selectors.LISTING_ADDR_STREET_NAME: _FakeLocator("Churchill"),
        selectors.LISTING_ADDR_TOWN: _FakeLocator("London"),
        selectors.LISTING_PRICE_RENT: _FakeLocator("1200"),
    }
    page = ZooplaCreateListingPage(_FakePage(fields), provider=None)

    asyncio.run(page._verify_and_correct_details(_listing()))

    assert all(loc.fills == [] for loc in fields.values())
