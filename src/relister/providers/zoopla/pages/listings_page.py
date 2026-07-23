from datetime import datetime
import logging
from typing import Any

from playwright.async_api import Page, TimeoutError as PWTimeoutError

from relister.domain.models import Address, LettingsListing, PropertyListing
from relister.providers.zoopla import selectors
from relister.providers.zoopla.mapper import parse_rent
from pydantic import HttpUrl

logger = logging.getLogger(__name__)


class ZooplaManagedListingsPage:
    def __init__(self, page: Page) -> None:
        self.page = page

    async def try_wait_for_locator(
        self,
        locator: str,
        *,
        extract_attribute: str | None = None,
        extract_text: bool = False,
        timeout: int = 2_000,
    ) -> Any:
        """_summary_

        Args:
            locator (str): the locator to find
            extract_attribute (str | None, optional): the attribute to extract. Defaults to None.
            extract_text (bool, optional): whether to extract text. Defaults to False.
            timeout (int, optional): the timeout in milliseconds. Defaults to 2_000.

        Returns:
            Any: the extracted value or None
        """
        try:
            element = self.page.locator(locator)
            if extract_attribute:
                return await element.get_attribute(extract_attribute, timeout=timeout)
            if extract_text:
                text = await element.text_content(timeout=timeout)
                # if not text:
                #     return await element.text_content(timeout=timeout)
                return text
            return element
        except PWTimeoutError:
            return None

    async def scrape(self, managed_listings_url: str) -> list[LettingsListing]:
        await self.page.goto(
            managed_listings_url,
            wait_until="domcontentloaded",
        )

        logger.debug("Waiting for login guard to complete...")

        if (login_gate := getattr(self.page.context, "login_gate", None)) is not None:
            await login_gate.wait_until_ready(self.page)
            logger.debug("Login guard completed. Proceeding with scraping.")

        ROW_ITEM = "tbody.listing_page_results > tr:not(.performance-report-row)"
        ITEM_STATUS = "//span[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'rent')]"

        row_locators = await self.page.locator(ROW_ITEM).all()

        listings = []
        for row_locator in row_locators:
            _href = await row_locator.get_attribute("data-edit-href")
            if not _href:
                logger.warning(
                    "Row does not have a data-edit-href attribute. Skipping row."
                )
                continue

            url = "https://pro.zoopla.co.uk/" + _href.lstrip("/")

            # Extract listing details from each row
            # ... (existing code for extracting details)

        # Address:
        postcode = await self.try_wait_for_locator(
            selectors.LISTING_ADDR_POSTCODE, extract_attribute="value"
        )
        property_number = await self.try_wait_for_locator(
            selectors.LISTING_ADDR_PROPERTY_NUMBER, extract_attribute="value"
        )
        street_name = await self.try_wait_for_locator(
            selectors.LISTING_ADDR_STREET_NAME, extract_attribute="value"
        )
        town = await self.try_wait_for_locator(
            selectors.LISTING_ADDR_TOWN, extract_attribute="value"
        )

        address = Address(
            house_number=property_number,
            street_name=str(street_name),
            town=str(town),
            postcode=str(postcode),
        )

        # Property Details:
        property_type = await self.try_wait_for_locator(
            selectors.LISTING_PROPERTY_TYPE, extract_text=True
        )
        property_type_checkboxes = [
            await self.page.locator(selector).is_checked()
            for selector in selectors.LISTING_PROPERTY_CHECKBOXES
        ]

        try:
            council_tax_band = await self.try_wait_for_locator(
                selectors.LISTING_PROPERTY_COUNCIL_TAX_BAND, extract_text=True
            )
            if council_tax_band == "Choose...":
                council_tax_band = None
        except PWTimeoutError:
            council_tax_band = None

        council_tax_exempt = await self.page.locator(
            selectors.LISTING_PROPERTY_COUNCIL_TAX_EXEMPT
        ).is_checked()

        # Price:
        price_modifier = await self.try_wait_for_locator(
            selectors.LISTING_RENT_FREQ, extract_text=True
        )
        price = await self.try_wait_for_locator(
            selectors.LISTING_PRICE_RENT, extract_attribute="value"
        )
        price = parse_rent(price or "", price_modifier)

        # Description:
        if property_type == "Studio":
            bedrooms = 0
        else:
            bedrooms = await self.try_wait_for_locator(
                selectors.LISTING_DESC_BEDROOMS, extract_text=True
            )
        bathrooms = await self.try_wait_for_locator(
            selectors.LISTING_DESC_BATHROOMS, extract_text=True
        )
        receptions = await self.try_wait_for_locator(
            selectors.LISTING_DESC_RECEPTIONS, extract_text=True
        )
        if not receptions:
            receptions = "N/A"
        floors = await self.try_wait_for_locator(
            selectors.LISTING_DESC_FLOORS, extract_text=True
        )
        if not floors:
            floors = "N/A"

        furnished = await self.try_wait_for_locator(
            selectors.LISTING_DESC_FURNISHED, extract_text=True
        )
        if not furnished or furnished == "Choose...":
            furnished = "Unfurnished"  # Default to Unfurnished if not specified

        available_from = await self.try_wait_for_locator(
            selectors.LISTING_DESC_AVAILABLE_FROM, extract_attribute="value"
        )
        available_from = (
            datetime.strptime(available_from, "%d/%m/%Y").date()
            if available_from
            else datetime.now().date()
        )

        summary = await self.try_wait_for_locator(
            selectors.LISTING_DESC_SUMMARY, extract_text=True
        )
        description = await self.try_wait_for_locator(
            selectors.LISTING_DESC_LONG_DESC, extract_text=True
        )

        # Features:
        features_bills_included = [
            await locator.is_checked()
            for locator in await self.page.locator(
                selectors.LISTING_FEATURES_BILLS_INCLUDED
            ).all()
        ]
        features_outside_space = [
            await locator.is_checked()
            for locator in await self.page.locator(
                selectors.LISTING_FEATURES_OUTSIDE_SPACE
            ).all()
        ]
        features_parking = [
            await locator.is_checked()
            for locator in await self.page.locator(
                selectors.LISTING_FEATURES_PARKING
            ).all()
        ]
        features_accessibility = [
            await locator.is_checked()
            for locator in await self.page.locator(
                selectors.LISTING_FEATURES_ACCESSIBILITY
            ).all()
        ]
        features_other = [
            await locator.is_checked()
            for locator in await self.page.locator(
                selectors.LISTING_FEATURES_OTHER
            ).all()
        ]

        #         print("Scraped listing details:")
        #         print(f"""{address=}
        #                 {property_type=}
        #                 {property_type_checkboxes=}
        #                 {council_tax_band=}
        #                 {council_tax_exempt=}
        #                 {price=}
        #                 {price_modifier=}
        #                 {bedrooms=}
        #                 {bathrooms=}
        #                 {receptions=}
        #                 {floors=}
        #                 {furnished=}
        #                 {available_from=}
        #                 {summary=}
        #                 {description=}
        #                 {features_bills_included=}
        #                 {features_outside_space=}
        #                 {features_parking=}
        #                 {features_accessibility=}
        #                 {features_other=}
        # """)

        listing = PropertyListing(
            source_provider="zoopla",
            source_url=(
                HttpUrl(managed_listings_url.strip())
                if not managed_listings_url.startswith("file://")
                else managed_listings_url.strip()
            ),
            address=address,
            property_type=property_type,
            summary=summary or "",
            description=description or "",
            property_type_checkboxes=property_type_checkboxes,
            rent_pcm=price,
            bedrooms=int(bedrooms),
            bathrooms=int(bathrooms),
            receptions=receptions,
            floors=floors,
            furnished=furnished,
            available_from=available_from,
            council_tax_band="X" if council_tax_exempt else council_tax_band,
            features=[
                features_bills_included,
                features_outside_space,
                features_parking,
                features_accessibility,
                features_other,
            ],
        )
        logger.debug("Scraped listing details: %s", listing)
        return []
