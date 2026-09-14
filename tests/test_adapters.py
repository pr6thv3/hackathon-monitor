"""Unit tests for pluggable college adapters."""

from src.adapters.base import CollegePortalAdapter, RawEvent
from src.adapters.vit import VITEventHubAdapter
from src.adapters.generic import GenericPlaywrightAdapter


def test_raw_event_dataclass():
    """Verify RawEvent initialization."""
    raw = RawEvent(
        title="VIT Hackathon",
        link="https://eventhub.vit.ac.in/event/1",
        date_text="2026-10-10",
        description="Campus build contest",
        category="Hackathon"
    )
    assert raw.title == "VIT Hackathon"
    assert raw.category == "Hackathon"


def test_adapter_inheritance():
    """Verify adapters inherit from CollegePortalAdapter."""
    vit_adapter = VITEventHubAdapter()
    assert isinstance(vit_adapter, CollegePortalAdapter)
    assert vit_adapter.adapter_id == "vit_eventhub"

    generic_adapter = GenericPlaywrightAdapter()
    assert isinstance(generic_adapter, CollegePortalAdapter)
    assert generic_adapter.adapter_id == "generic"
