"""Shared data model for a single job listing, regardless of source repo."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Listing:
    id: str
    source: str
    company: str
    title: str
    location: str
    url: str
    date_posted: str
