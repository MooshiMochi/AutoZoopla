# src/relister/domain/models.py

from datetime import date
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, Field, HttpUrl


class Address(BaseModel):
    house_number: str | None = None
    street_name: str
    town: str
    postcode: str

    def __str__(self) -> str:
        return f"<Address {self.house_number} {self.street_name}, {self.town} {self.postcode}>"


class ListingImage(BaseModel):
    source_url: HttpUrl | None = None
    local_path: Path | None = None
    position: int = 0
    caption: str | None = None


class PropertyListing(BaseModel):
    source_provider: str
    source_listing_id: str | None = None
    source_url: HttpUrl | str | None = None

    address: Address
    summary: str
    description: str
    property_type_checkboxes: list[bool] = Field(default_factory=list)

    rent_pcm: Decimal = Field(gt=0)

    bedrooms: int = Field(ge=0)
    bathrooms: int = Field(ge=0)
    receptions: str
    floors: str
    property_type: str

    furnished: str | None = None
    available_from: date | None = None
    council_tax_band: str | None = None

    features: list[list[str]] | list[list[bool]] = Field(default_factory=list)
    images: list[ListingImage] = Field(default_factory=list)

    agent_reference: str | None = None

    def __str__(self) -> str:
        return (
            f"<PropertyListing {self.address} | ({self.source_provider})\nDetails:{{\n    "
            f"        Summary: {self.summary}\n"
            f"        Description: {self.description}\n"
            f"        Property Type Checkboxes: {self.property_type_checkboxes}\n"
            f"        Rent: {self.rent_pcm}\n"
            f"        Bedrooms: {self.bedrooms}\n"
            f"        Bathrooms: {self.bathrooms}\n"
            f"        Receptions: {self.receptions}\n"
            f"        Floors: {self.floors}\n"
            f"        Property Type: {self.property_type}\n"
            f"        Furnished: {self.furnished}\n"
            f"        Available From: {self.available_from}\n"
            f"        Council Tax Band: {self.council_tax_band}\n"
            f"        Features: {self.features}\n"
            f"        Images: {self.images}\n"
            f"        Agent Reference: {self.agent_reference}\n"
            f"        Source Listing ID: {self.source_listing_id}\n"
            f"        Source URL: {self.source_url}"
            "}}>"
        )


class LettingsListing(BaseModel): ...
