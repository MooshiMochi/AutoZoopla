# Handle provider specific formatting

import re
from decimal import Decimal


def parse_rent(value: str, modifier: str) -> Decimal:
    cleaned = re.sub(r"[^\d.]", "", value)

    if not cleaned:
        raise ValueError(f"Could not parse rent from {value!r}")

    num = Decimal(cleaned)

    multiplier = {
        "Weekly": 52 / 12,
        "Monthly": 1,
        "Annually": 1 / 12,
    }.get(modifier.lower(), 1)

    return num * multiplier
