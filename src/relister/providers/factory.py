# src/relister/providers/factory.py

from relister.providers.base import PropertyProvider
from relister.providers.zoopla.provider import ZooplaProvider
from relister.core.config import Settings


def get_provider(name: str, *, destination: bool = False) -> PropertyProvider:
    settings = Settings()
    providers: dict[str, PropertyProvider] = {
        "zoopla": ZooplaProvider(
            username=(
                settings.zoopla_destination_username
                if destination
                else settings.zoopla_source_username
            ),
            password=(
                settings.zoopla_destination_password
                if destination
                else settings.zoopla_source_password
            ),
        ),
        # "onthemarket": OnthemarketProvider,  # TODO: Implement OnTheMarketProvider
    }

    try:
        provider_class = providers[name.lower()]
    except KeyError as exc:
        supported = ", ".join(providers)

        raise ValueError(
            f"Unsupported provider: {name}. " f"Supported providers: {supported}"
        ) from exc

    return provider_class
