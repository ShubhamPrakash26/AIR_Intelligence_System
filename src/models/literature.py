"""Data model for clinical literature documents (guidelines, papers, protocols).

Literature documents are stored in the same Qdrant collection as incident
reports, distinguished by VectorMetadata.source_type = "literature" |
"guideline" | "protocol".  This allows the existing RAG pipeline to retrieve
from both corpora in a single query, with optional source_type filtering.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class LiteratureDocument:
    """Structured representation of a clinical literature document.

    Attributes:
        document_id: UUID string — assigned by the parser on creation.
        title: Full document title.
        content: Main embeddable text (abstract, summary, or full body).
        source_type: Discriminator — "literature", "guideline", or "protocol".
        authors: Author name list (may be empty for anonymised guidelines).
        year: Publication year (None when unknown).
        doi: Digital Object Identifier (None when not applicable).
        journal: Journal or publisher name.
        keywords: Subject keywords extracted from metadata or content.
        raw_data: Original parsed fields preserved for audit.
    """

    document_id: str
    title: str
    content: str
    source_type: str  # "literature" | "guideline" | "protocol"
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    journal: str | None = None
    keywords: list[str] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        title: str,
        content: str,
        source_type: str = "literature",
        **kwargs: Any,
    ) -> "LiteratureDocument":
        """Factory that auto-assigns a UUID document_id."""
        return cls(
            document_id=str(uuid.uuid4()),
            title=title,
            content=content,
            source_type=source_type,
            **kwargs,
        )

    @property
    def embeddable_text(self) -> str:
        """Return the text that should be embedded — title + content."""
        parts = [self.title]
        if self.keywords:
            parts.append("Keywords: " + ", ".join(self.keywords))
        parts.append(self.content)
        return "\n\n".join(filter(None, parts))

    @property
    def citation_string(self) -> str:
        """Return a compact citation string for display in editorial context."""
        authors_str = ", ".join(self.authors[:3])
        if len(self.authors) > 3:
            authors_str += " et al."
        year_str = f" ({self.year})" if self.year else ""
        journal_str = f". {self.journal}" if self.journal else ""
        doi_str = f". doi:{self.doi}" if self.doi else ""
        return f"{authors_str}{year_str}. {self.title}{journal_str}{doi_str}".strip(". ")
