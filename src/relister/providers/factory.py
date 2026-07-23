# src/relister/providers/factory.py

from relister.providers.base import PropertyProvider
from relister.providers.zoopla.provider import ZooplaProvider
from relister.storage.credentials import CredentialStore

_PROVIDER_CLASSES: dict[str, type[PropertyProvider]] = {
    "zoopla": ZooplaProvider,
    # "onthemarket": OnthemarketProvider,  # TODO: Implement OnTheMarketProvider
}


def provider_class_for(name: str) -> type[PropertyProvider] | None:
    """Return the provider class for ``name`` without constructing it.

    Useful for credential-free operations such as listing-ID extraction.
    """

    return _PROVIDER_CLASSES.get(name.lower())


def get_provider(name: str, *, destination: bool = False) -> PropertyProvider:
    role = "destination" if destination else "source"
    provider_class = provider_class_for(name)
    if provider_class is None:
        supported = ", ".join(_PROVIDER_CLASSES)
        raise ValueError(
            f"Unsupported provider: {name}. Supported providers: {supported}"
        )

    username, password = CredentialStore().get(name.lower(), role) or ("", "")
    return provider_class(username=username, password=password)
