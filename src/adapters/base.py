"""
Base interfaces and data structures for pluggable college portal adapters.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RawEvent:
    title: str
    link: str | None = None
    date_text: str | None = None
    description: str | None = None
    category: str | None = None
    organizer: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class CollegePortalAdapter(ABC):
    """
    Abstract base class for college portal scrapers.
    Each adapter encapsulates the authentication and DOM/API extraction
    for a specific university or generic event portal.
    """

    @property
    @abstractmethod
    def adapter_id(self) -> str:
        """Unique identifier for this adapter (e.g. 'vit_eventhub', 'generic')."""
        ...

    @abstractmethod
    def fetch_events(self, config: dict[str, Any]) -> str | None:
        """
        Fetch all events from the portal.
        Handles session restoration, authentication, and structured extraction.
        Returns formatted text summary ready for Stage 1 Gemini extraction, or None on failure.
        """
        ...
