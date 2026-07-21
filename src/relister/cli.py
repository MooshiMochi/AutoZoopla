import argparse
import asyncio
import logging
from os import path
from pathlib import Path

from relister.providers.factory import get_provider
from relister.logging_setup import configure_logging
from relister.workflows.relist_listing import relist_property

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="relister",
        description="Scrape and re-list property advertisements.",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    relist_parser = subparsers.add_parser(
        "relist",
        help="Scrape and re-list a property advertisement.",
    )

    relist_parser.add_argument(
        "--source",
        required=True,
        choices=["zoopla"],
        help="Provider containing the original listing.",
    )

    relist_parser.add_argument(
        "--destination",
        required=True,
        choices=["zoopla"],
        help="Provider where the new listing will be created.",
    )

    relist_parser.add_argument(
        "--url",
        required=True,
        help="URL of the original property listing.",
    )

    relist_parser.add_argument(
        "--images",
        help="Path to a directory containing images to upload for the new listing.",
    )

    relist_parser.add_argument(
        "--publish",
        action="store_true",
        help="Publish the listing. Without this flag, a dry run is used.",
    )

    relist_parser.add_argument(
        "--headless",
        action="store_true",
        help="Run the browser without a visible window.",
    )

    relist_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )

    return parser


async def run_relist(args: argparse.Namespace) -> None:
    source_provider = get_provider(args.source)
    destination_provider = get_provider(args.destination, destination=True)
    images_path = Path(args.images) if args.images else None

    if images_path:
        if not images_path.is_dir():
            logger.error(
                "The specified images path is not a directory. Please supply the folder containing the images to upload."
            )
            return

        if not Path.joinpath(images_path, "instructions.txt").exists():
            logger.error(
                "instructions.txt file not found in the images directory. "
                "Please ensure that the file exists and contains the necessary instructions."
            )
            return

    result = await relist_property(
        source_provider=source_provider,
        destination_provider=destination_provider,
        listing_url=args.url,
        images_path=images_path,
        dry_run=not args.publish,
        headless=args.headless,
    )

    logger.info(
        "Property: %s, %s %s",
        result.listing.address.street_name,
        result.listing.address.town,
        result.listing.address.postcode,
    )
    logger.info("Rent: £%s PCM", result.listing.rent_pcm)

    if result.published:
        logger.info(
            "Listing published successfully. Destination ID: %s",
            result.destination_listing_id,
        )
        if result.destination_listing_url:
            logger.info("New listing URL: %s", result.destination_listing_url)
    else:
        logger.info("Dry run completed. No listing was published.")


async def async_main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    configure_logging(verbose=getattr(args, "verbose", False))

    if args.command == "relist":
        await run_relist(args)


def main() -> None:
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.warning("Relist process cancelled.")
        raise SystemExit(130)
    except Exception as exc:
        logger.exception("Relist process failed")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
