from relister.providers.base import PropertyProvider
from relister.providers.factory import provider_class_for
from relister.providers.zoopla.provider import ZooplaProvider


def test_zoopla_extracts_plain_id():
    url = "https://pro.zoopla.co.uk/properties/listing/5356300"
    assert ZooplaProvider.extract_listing_id(url) == "5356300"


def test_trailing_slash_and_query_are_stripped():
    assert (
        ZooplaProvider.extract_listing_id(
            "https://pro.zoopla.co.uk/properties/listing/5356300/?x=1"
        )
        == "5356300"
    )


def test_empty_url_is_none():
    assert ZooplaProvider.extract_listing_id("") is None


def test_base_default_takes_last_segment():
    assert PropertyProvider.extract_listing_id("https://x/y/42") == "42"


def test_provider_class_lookup():
    assert provider_class_for("zoopla") is ZooplaProvider
    assert provider_class_for("nope") is None
