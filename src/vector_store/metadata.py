"""Metadata extraction and payload helpers for the Qdrant vector store.

Each incident vector is stored alongside a structured payload so that
similarity search results can be filtered and interpreted without re-fetching
the source record from the database.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.models.analysis import AIAnalysis, VectorMetadata
from src.models.incident import Incident


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
        incident_type = incident.incident.incident_type or ["Unknown"]
        severity = incident.outcome.harm_severity or "Unknown"
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


def build_payload(metadata: VectorMetadata) -> dict:
    """Convert VectorMetadata to a flat JSON-serialisable dict for Qdrant.

    The returned dict is suitable for use as a Qdrant point payload.
    Lists are kept as-is because Qdrant supports array field filtering.
    """
    return metadata.model_dump(mode="json")
