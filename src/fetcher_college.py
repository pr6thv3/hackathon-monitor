"""
College Event Fetcher Gateway.

Routes scraping requests to the appropriate CollegePortalAdapter
(e.g. VITEventHubAdapter, GenericPlaywrightAdapter).
Maintains backwards compatibility with existing pipeline orchestrator.
"""

import logging
from typing import Any
from src.adapters.vit import VITEventHubAdapter
from src.adapters.generic import GenericPlaywrightAdapter

log = logging.getLogger(__name__)


def fetch_college_events(portal_config: dict[str, Any] = None) -> str | None:
    """
    Fetch college events using the configured portal adapter.
    Defaults to VITEventHubAdapter if no specific adapter is declared.
    """
    cfg = portal_config or {}
    adapter_type = cfg.get("adapter", "vit_eventhub").lower()

    log.info(f"Dispatching college event fetch using adapter '{adapter_type}'...")

    if adapter_type == "vit_eventhub":
        adapter = VITEventHubAdapter()
        return adapter.fetch_events(cfg)
    elif adapter_type in ("generic", "playwright", "generic_playwright"):
        adapter = GenericPlaywrightAdapter()
        return adapter.fetch_events(cfg)
    else:
        log.warning(f"Unknown portal adapter '{adapter_type}' — falling back to VITEventHubAdapter")
        adapter = VITEventHubAdapter()
        return adapter.fetch_events(cfg)
