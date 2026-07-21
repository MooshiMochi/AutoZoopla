# src/relister/workflows/relist_listing.py
from pathlib import Path
from relister.browser.session import BrowserSession
from relister.domain.models import PropertyListing
from relister.providers.base import PropertyProvider


class RelistResult:
    def __init__(
        self,
        listing: PropertyListing,
        destination_listing_id: str | None,
        destination_listing_url: str | None,
        published: bool,
    ) -> None:
        self.listing = listing
        self.destination_listing_id = destination_listing_id
        self.destination_listing_url = destination_listing_url
        self.published = published


def validate_listing_for_publication(listing: PropertyListing) -> None:
    if not listing.address.house_number and not listing.address.street_name:
        raise ValueError("Listing is missing an address")

    if listing.rent_pcm <= 0:
        raise ValueError("Listing rent must be greater than zero")


async def relist_property(
    source_provider: PropertyProvider,
    destination_provider: PropertyProvider,
    listing_url: str,
    images_path: Path | None = None,
    *,
    dry_run: bool = True,
    headless: bool = False,
) -> RelistResult:

    source_session = BrowserSession(
        provider=source_provider,
        headless=headless,
    )

    async with source_session.authenticated_context() as context:
        # async with source_session.authenticated_context() as context:
        listing = await source_provider.scrape_listing(
            context=context,
            listing_url=listing_url,
        )

        validate_listing_for_publication(listing)

        deleted = await source_provider.delete_listing(
            context=context, listing_url=listing_url, submit=not dry_run
        )

    if not deleted:
        raise RuntimeError(
            f"Failed to delete listing at {listing_url}. Please try again later."
        )

    destination_session = BrowserSession(
        provider=destination_provider,
        headless=headless,
    )

    async with destination_session.authenticated_context() as context:
        reference = listing.agent_reference or listing.source_listing_id

        if reference:
            already_exists = await destination_provider.listing_exists(
                context=context,
                reference=reference,
            )

            if already_exists:
                raise RuntimeError(f"Listing {reference!r} already exists")

        destination_listing_id = await destination_provider.create_listing(
            context=context,
            listing=listing,
            images_path=images_path,
            submit=not dry_run,
        )

    return RelistResult(
        listing=listing,
        destination_listing_id=(
            destination_listing_id[0] if destination_listing_id else None
        ),
        destination_listing_url=(
            destination_listing_id[1] if destination_listing_id else None
        ),
        published=not dry_run and destination_listing_id is not None,
    )
