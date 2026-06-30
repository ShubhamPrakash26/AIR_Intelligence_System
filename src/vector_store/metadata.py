"""Metadata extraction and payload helpers for the Qdrant vector store.

Each incident vector is stored alongside a structured payload so that
similarity search results can be filtered and interpreted without re-fetching
the source record from the database.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.models.analysis import AIAnalysis, VectorMetadata
from src.models.incident import Incident
from src.models.literature import LiteratureDocument


def extract_metadata(
    incident: Incident,
    analysis: AIAnalysis | None = None,
) -> VectorMetadata:
    """Build a VectorMetadata payload from an Incident and optional analysis.

    When ``analysis`` is provided, classification and severity fields are taken
    from it (preferred).  When absent, raw incident fields are used as a
    best-effort fallback so incidents can be indexed before analysis completes.

    Args:
        incident: Parsed incident record.
        analysis: Optional AI analysis produced by the understanding agent.

    Returns:
        VectorMetadata ready for storage in Qdrant.
    """
    now = datetime.now(timezone.utc).isoformat()

    if analysis:
        incident_type = analysis.incident_type
        severity = analysis.severity
        severity_score = analysis.severity_score
        root_cause = analysis.root_cause
        key_learning = analysis.key_learning
    else:
        # Graceful fallback when analysis is not yet available
        incident_type = incident.incident.incident_type or []
        severity = incident.outcome.harm_severity or ""
        severity_score = 0.0
        root_cause = ""
        key_learning = ""

    return VectorMetadata(
        incident_id=incident.incident_id,
        incident_type=incident_type,
        severity=severity,
        severity_score=severity_score,
        surgery_type=incident.surgery.surgical_branch or "Unknown",
        root_cause=root_cause,
        key_learning=key_learning,
        month=incident.metadata.month,
        year=incident.metadata.year,
        source=incident.metadata.source_file or "unknown",
        timestamp=now,
    )


def extract_literature_metadata(document: LiteratureDocument) -> VectorMetadata:
    """Build a VectorMetadata payload from a LiteratureDocument.

    Maps literature document fields onto the VectorMetadata schema so that
    documents can coexist with incident reports in the same Qdrant collection.
    The ``source_type`` field distinguishes them from incident reports.

    Field mapping:
        incident_id   → document.document_id
        incident_type → document.keywords (capped at 5) or ["Literature"]
        severity      → "Reference"   (not applicable for literature)
        surgery_type  → "Literature"  (not a clinical incident)
        root_cause    → first 500 chars of document.content (abstract/summary)
        key_learning  → document.citation_string
        title         → document.title
        source_type   → document.source_type
        source        → document.doi or document.journal or document.raw_data source_file
    """
    now = datetime.now(timezone.utc).isoformat()

    incident_types = (
        document.keywords[:5] if document.keywords else ["Literature"]
    )

    source = (
        document.doi
        or document.journal
        or document.raw_data.get("source_file", "unknown")
    )

    return VectorMetadata(
        incident_id=document.document_id,
        incident_type=incident_types,
        severity="Reference",
        severity_score=0.0,
        surgery_type="Literature",
        root_cause=document.content[:500],
        key_learning=document.citation_string,
        month=str(document.year) if document.year else None,
        year=document.year,
        source=source or "unknown",
        timestamp=now,
        source_type=document.source_type,
        title=document.title,
    )


def build_payload(metadata: VectorMetadata) -> dict:
    """Convert VectorMetadata to a flat JSON-serialisable dict for Qdrant.

    The returned dict is suitable for use as a Qdrant point payload.
    Lists are kept as-is because Qdrant supports array field filtering.
    """
    return metadata.model_dump(mode="json")
