# src/relister/providers/zoopla/pages/create_listing_page.py

import asyncio
import logging
from pathlib import Path

from playwright.async_api import Page, Locator, TimeoutError as PWTimeoutError

from relister.domain.models import PropertyListing
from relister.providers.zoopla import selectors

logger = logging.getLogger(__name__)


class ZooplaCreateListingPage:
    def __init__(self, page: Page, provider) -> None:
        self.page = page
        self.provider = provider
        self._new_listing_created: bool = False
        self._save_new_listing_btn: Locator | None = None

    def _remove_selected_option_prefix(self, select_element: str) -> str:
        return select_element.removesuffix("> option[selected]").strip()

    async def _wait_for_creation_success(self) -> tuple[str, str]:
        await self.page.wait_for_load_state("networkidle")
        await self.page.locator("div.alert-success:has(strong)").wait_for(
            state="visible",
            timeout=10_000,
        )
        _id = self.extract_listing_id(self.page.url)
        return _id, selectors.AGENT_LISTING_URL_FMT.format(_id=_id)

    async def fill_listing_details(
        self, listing: PropertyListing, images_path: Path | None = None
    ) -> None:
        await self.set_listing_status(listing)
        await self.fill_property_address(listing)
        await self.fill_property_details(listing)
        await self.fill_price_details(listing)
        await self.fill_description(listing)
        await self.fill_features(listing)
        await self.upload_images(listing, images_path)

    async def _open_create_listing_page(self) -> None:
        await self.page.goto(
            selectors.CREATE_LISTING_URL,
            wait_until="domcontentloaded",
        )

    async def _submit_listing(self) -> None:
        save_button = self.page.get_by_role("button", name="save").first
        await save_button.click()

    async def _handle_submission_timeout(
        self, listing: PropertyListing, attempt: int, exc: Exception
    ) -> bool:
        try:
            await self.page.locator("div.alert > strong").wait_for(
                state="visible",
                timeout=10_000,
            )
            logger.warning("Listing creation failed. Refilling the form for retry.")
            await self.fill_listing_details(listing)
            logger.warning("Waiting 5 seconds before retrying to submit the form.")
            await asyncio.sleep(5)
            return True

        except PWTimeoutError:
            logger.warning(
                "Neither success nor failure indicators appeared within the timeout. Please review the page to ensure the listing was created successfully."
            )
            if attempt == 1:
                raise RuntimeError("Failed to create listing after retry.") from exc

            logger.warning(
                "Success indicator did not appear within the timeout. Please review the page to ensure the listing was created successfully."
            )

            # pause_task = asyncio.create_task(self.page.pause())
            # try:
            result = await asyncio.to_thread(
                input,
                "Should we re-fill the details? (y/n): ",
            )
            # finally:
            # pause_task.cancel()

            if result.lower() != "y":
                raise RuntimeError("Listing creation aborted by user.") from exc

            await self.fill_listing_details(listing)

            await self._save_filled_screenshot()
            return True

    async def _save_filled_screenshot(self) -> None:
        """Best-effort debug screenshot to a writable app-data location.

        Never aborts the relist: a hardcoded relative path (``data/...``) would
        resolve under a read-only ``/`` when the app is launched from Finder.
        """

        try:
            from relister.core import paths

            target = paths.data_dir() / "screenshots" / "filled-listing.png"
            target.parent.mkdir(parents=True, exist_ok=True)
            await self.page.screenshot(path=str(target), full_page=True)
        except Exception as exc:
            logger.warning("Could not save the debug screenshot: %s", exc)

    async def create(
        self,
        listing: PropertyListing,
        images_path: Path | None = None,
        *,
        submit: bool,
    ) -> tuple[str, str] | None:
        await self._open_create_listing_page()
        await self.fill_listing_details(listing, images_path)

        await self._save_filled_screenshot()

        if not submit:
            logger.info("Dry run complete. The form has been filled but not submitted.")
            await self.page.pause()
            return None

        for attempt in range(2):
            try:
                await self._submit_listing()
            except PWTimeoutError:
                pass

            try:
                return await self._wait_for_creation_success()
            except PWTimeoutError as exc:
                if not await self._handle_submission_timeout(listing, attempt, exc):
                    raise
        raise RuntimeError("Failed to create listing after retry.")

    async def set_listing_status(self, listing: PropertyListing):
        await self.page.locator("select#status").select_option("public")
        await self.page.locator("select#listing_status").select_option("to_rent")

    async def fill_property_address(self, listing: PropertyListing) -> None:
        await self.page.locator(selectors.LISTING_ADDR_POSTCODE).fill(
            listing.address.postcode
        )
        await self.page.locator(selectors.LISTING_ADDR_PROPERTY_NUMBER).fill(
            listing.address.house_number or ""
        )
        await self.page.locator(selectors.LISTING_ADDR_STREET_NAME).fill(
            listing.address.street_name or ""
        )
        await self.page.locator(selectors.LISTING_ADDR_TOWN).fill(
            listing.address.town or ""
        )

    async def fill_property_details(
        self,
        listing: PropertyListing,
    ) -> None:
        await self.page.locator(
            self._remove_selected_option_prefix(selectors.LISTING_PROPERTY_TYPE)
        ).select_option(listing.property_type)
        if listing.council_tax_band == "X":
            await self.page.locator(
                self._remove_selected_option_prefix(
                    selectors.LISTING_PROPERTY_COUNCIL_TAX_EXEMPT
                )
            ).check()
        elif listing.council_tax_band:
            await self.page.locator(
                self._remove_selected_option_prefix(
                    selectors.LISTING_PROPERTY_COUNCIL_TAX_BAND
                )
            ).select_option(listing.council_tax_band)

        for checkbox, is_checked in zip(
            selectors.LISTING_PROPERTY_CHECKBOXES,
            listing.property_type_checkboxes,
        ):
            if is_checked:
                await self.page.locator(checkbox).check()

    async def fill_price_details(
        self,
        listing: PropertyListing,
    ) -> None:
        await self.page.locator(selectors.LISTING_PRICE_RENT).fill(
            str(listing.rent_pcm)
        )
        await self.page.locator(
            self._remove_selected_option_prefix(selectors.LISTING_RENT_FREQ)
        ).select_option("per_month")

    async def fill_description(
        self,
        listing: PropertyListing,
    ) -> None:
        if not listing.property_type == "Studio":
            await self.page.locator(
                self._remove_selected_option_prefix(selectors.LISTING_DESC_BEDROOMS)
            ).select_option(str(listing.bedrooms))

        await self.page.locator(
            self._remove_selected_option_prefix(selectors.LISTING_DESC_BATHROOMS)
        ).select_option(str(listing.bathrooms))
        await self.page.locator(
            self._remove_selected_option_prefix(selectors.LISTING_DESC_RECEPTIONS)
        ).select_option(str(listing.receptions))
        await self.page.locator(
            self._remove_selected_option_prefix(selectors.LISTING_DESC_FLOORS)
        ).select_option(str(listing.floors))
        if listing.furnished:
            await self.page.locator(
                self._remove_selected_option_prefix(selectors.LISTING_DESC_FURNISHED)
            ).select_option(listing.furnished)
        if listing.available_from:

            if listing.available_from < listing.available_from.today():
                listing.available_from = listing.available_from.today()

            await self.page.locator(selectors.LISTING_DESC_AVAILABLE_FROM).evaluate(
                """(el, value) => el.value = value""",
                listing.available_from.strftime("%d/%m/%Y"),
            )

        await self.page.locator(selectors.LISTING_DESC_SUMMARY).fill(listing.summary)
        await self.page.locator(selectors.LISTING_DESC_LONG_DESC).fill(
            listing.description
        )

    async def fill_features(
        self,
        listing: PropertyListing,
    ) -> None:
        if not listing.features:
            return

        for features, locator in zip(
            listing.features,
            [
                selectors.LISTING_FEATURES_BILLS_INCLUDED,
                selectors.LISTING_FEATURES_OUTSIDE_SPACE,
                selectors.LISTING_FEATURES_PARKING,
                selectors.LISTING_FEATURES_ACCESSIBILITY,
                selectors.LISTING_FEATURES_OTHER,
            ],
        ):
            for feature, is_checked in zip(
                await self.page.locator(locator).all(), features
            ):
                if is_checked:
                    await feature.check()

    async def upload_images(
        self,
        listing: PropertyListing,
        images_path: Path | None = None,
    ) -> None:
        if not images_path:
            logger.info("No images path provided. Skipping image upload.")
            return
        paths = self._load_images_from_instructions(images_path) if images_path else []

        if not paths:
            raise ValueError("No downloaded images are available for upload")

        logger.info("Uploading %d images for listing: %s", len(paths), listing.address)
        images_input_locator = self.page.locator(selectors.LISTING_IMAGE_UPLOAD_INPUT)

        await images_input_locator.scroll_into_view_if_needed()
        await images_input_locator.set_input_files(paths)

        await self.manage_image_upload_progress(len(paths))

    async def manage_image_upload_progress(self, num_images: int) -> None:
        count = 1
        while (
            await self.page.locator(f"p#image_loading_{num_images}").is_visible()
            and count <= num_images
        ):
            await asyncio.sleep(1)
            image_loading_id = f"image_loading_{count}"
            try:
                await self.page.locator(f"p#{image_loading_id}").wait_for(
                    state="detached", timeout=30_000
                )
                logger.info(f"Image {count}/{num_images} uploaded successfully.")
            except PWTimeoutError:
                logger.warning(
                    f"Timeout while waiting for image {count}/{num_images} to upload. Please check the page for any issues."
                )
            count += 1

    def _load_images_from_instructions(self, images_path: Path) -> list[Path]:
        instructions_file = images_path / "instructions.txt"
        if not instructions_file.exists():
            raise FileNotFoundError(
                f"Instructions file not found at {instructions_file}"
            )

        with open(instructions_file, "r") as f:
            image_filenames = [line.strip() for line in f.readlines()]

        image_paths = []
        for filename in image_filenames:
            image_path = images_path / filename
            if not image_path.exists():
                raise FileNotFoundError(f"Image file not found: {image_path}")
            image_paths.append(image_path)

        return image_paths

    @staticmethod
    def extract_listing_id(url: str) -> str:
        from relister.providers.zoopla.provider import ZooplaProvider

        return ZooplaProvider.extract_listing_id(url) or ""
