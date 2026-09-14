"""
College Portal Adapters Package.
"""

from src.adapters.base import CollegePortalAdapter, RawEvent
from src.adapters.vit import VITEventHubAdapter
from src.adapters.generic import GenericPlaywrightAdapter

__all__ = [
    "CollegePortalAdapter",
    "RawEvent",
    "VITEventHubAdapter",
    "GenericPlaywrightAdapter",
]
