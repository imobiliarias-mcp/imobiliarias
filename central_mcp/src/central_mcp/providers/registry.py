"""Provider Registry for Central Rental Research MCP."""

from pathlib import Path
from typing import Any

from central_mcp.domain.collections import ProviderCatalog
from central_mcp.domain.entities import ProviderSpec
from central_mcp.domain.value_objects import ProviderId
from central_mcp.providers.venv_adapter import LocalVenvAdapter

PROVIDER_MAP: dict[str, str] = {
    "alecorretoramg": "AleCorretoraMcpAdapter",
    "arthusoimoveis": "ArthusoMcpAdapter",
    "cabralporto": "CabralPortoMcpAdapter",
    "casalinhares": "CasaLinharesMcpAdapter",
    "epifanioimoveis": "EpifanioMcpAdapter",
    "helenaimoveis": "HelenaMcpAdapter",
    "imobiliariaportalmg": "PortalMGMcpAdapter",
    "imobiliariavaleinvest": "ValeInvestMcpAdapter",
    "imovelweb": "ImovelwebMcpAdapter",
    "marcioimoveis": "MarcioMcpAdapter",
    "minascaixaimoveis": "MinasCaixaMcpAdapter",
    "niltoncorretordeimoveis": "NiltonMcpAdapter",
    "novaimobiliaria": "NovaMcpAdapter",
    "veraimobiliaria": "VeraMcpAdapter",
    "vivareal": "VivaRealMcpAdapter",
}


class ProviderRegistry:
    """Registry maintaining active and lazily-instantiated provider adapters."""

    def __init__(self, repo_root: Path | None = None) -> None:
        """Initialize registry with root directory and adapter cache."""
        self._root = repo_root or Path(__file__).resolve().parent.parent.parent.parent.parent
        self._instances: dict[str, Any] = {}

    @classmethod
    def create_default(cls, repo_root: Path | None = None) -> "ProviderRegistry":
        """Factory constructor instantiating the default provider registry."""
        return cls(repo_root=repo_root)

    def all_provider_ids(self) -> tuple[str, ...]:
        """Return tuple of all registered provider identifiers."""
        return tuple(PROVIDER_MAP.keys())

    def register(self, provider_id: str, adapter: Any) -> None:
        """Explicitly register or mock an adapter instance."""
        self._instances[provider_id] = adapter

    def get(self, provider_id: str) -> Any:
        """Retrieve or dynamically instantiate the provider adapter."""
        if provider_id not in PROVIDER_MAP and provider_id not in self._instances:
            raise KeyError(f"Unknown provider '{provider_id}'")
        if provider_id in self._instances:
            return self._instances[provider_id]
        adapter = self._instantiate_adapter(provider_id)
        self._instances[provider_id] = adapter
        return adapter

    def _instantiate_adapter(self, provider_id: str) -> Any:
        """Instantiate a local venv adapter for the provider."""
        class_name = PROVIDER_MAP[provider_id]
        agency_dir = self._root / provider_id
        return LocalVenvAdapter(agency_dir=agency_dir, adapter_class_name=class_name)

    def catalog(self) -> ProviderCatalog:
        """Build provider catalog describing metadata and supported operations."""
        specs: list[ProviderSpec] = []
        for pid in PROVIDER_MAP:
            spec = self._build_spec(pid)
            specs.append(spec)
        return ProviderCatalog(specs)

    def _build_spec(self, provider_id: str) -> ProviderSpec:
        """Build a ProviderSpec from adapter info or defaults."""
        info = self._get_info_safe(provider_id)
        cov = info.get("coverage_region", "Vale do Aço")
        ops = tuple(info.get("supported_operations", ["search_rentals", "get_property_detail", "get_facets"]))
        return ProviderSpec(
            identifier=ProviderId(provider_id),
            coverage_region=cov,
            supported_operations=ops,
        )

    def _get_info_safe(self, provider_id: str) -> dict[str, Any]:
        """Safely fetch provider info without failing if network is offline."""
        try:
            adapter = self.get(provider_id)
            if hasattr(adapter, "get_provider_info"):
                return adapter.get_provider_info()
            return {}
        except (KeyError, RuntimeError, OSError, ValueError):
            return {}

