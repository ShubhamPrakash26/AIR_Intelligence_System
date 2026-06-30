"""Anomaly detection for clinical incident vectors.

HDBSCAN labels any incident it cannot assign to a cluster as noise (label -1).
These noise points represent incidents whose combination of features is
statistically unusual relative to the rest of the dataset — no peer cluster
absorbed them.  This module surfaces those incidents as clinical anomalies.

The AnomalyDetector:
  - Runs UMAP + HDBSCAN (same pipeline as clustering)
  - Collects all noise-labelled incidents
  - Attaches HDBSCAN's per-point outlier score (0–1; higher = more anomalous)
    when available
  - Returns ranked AnomalyResult objects, most anomalous first

Typical use: POST /retrieval/anomalies — identifies rare/unusual incident
patterns that warrant additional clinical review.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from src.utils.logger import get_logger

logger = get_logger(__name__)

_ANOMALY_REASON = (
    "No matching incident cluster found. "
    "The combination of features (incident type, surgical context, severity) "
    "is statistically unusual relative to the rest of the dataset."
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class AnomalyResult:
    """A single incident flagged as anomalous (HDBSCAN noise point).

    Attributes:
        incident_id: UUID of the anomalous incident.
        outlier_score: HDBSCAN outlier score 0–1 (higher = more anomalous).
            Set to 0.0 when the scorer is unavailable (injected model).
        severity: Stored severity label.
        surgery_type: Surgical context.
        incident_type: Stored incident type list.
        root_cause: Stored root cause summary (truncated to 200 chars).
        source: Origin file.
        reason: Plain-text explanation for why this incident was flagged.
    """

    incident_id: str
    outlier_score: float
    severity: str
    surgery_type: str
    incident_type: list[str] = field(default_factory=list)
    root_cause: str = ""
    source: str = "unknown"
    reason: str = _ANOMALY_REASON


@dataclass
class AnomalyDetectionResult:
    """Output of a single anomaly detection run.

    Attributes:
        total_incidents: Number of incidents analysed.
        n_clusters: Clusters found (anomalies are the complement).
        n_anomalies: Number of noise-labelled incidents.
        anomaly_ratio: Fraction of incidents that are anomalous.
        anomalies: Ranked list (most anomalous first).
    """

    total_incidents: int
    n_clusters: int
    n_anomalies: int
    anomaly_ratio: float
    anomalies: list[AnomalyResult]


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


class AnomalyDetector:
    """Detect anomalous incidents using HDBSCAN noise-point labelling.

    Args:
        min_cluster_size: Minimum incidents to form a cluster (lower = more
            sensitive to patterns, fewer anomalies; default 3).
        auto_params: When True, override min_cluster_size with
            ``max(3, int(sqrt(n)))`` so it scales with dataset size.
        umap_model: Injectable UMAP-like model for testing (``fit_transform``).
        hdbscan_model: Injectable HDBSCAN-like model for testing
            (``fit_predict``; must expose ``.outlier_scores_`` after fit).
    """

    def __init__(
        self,
        min_cluster_size: int = 3,
        auto_params: bool = False,
        umap_model: Any = None,
        hdbscan_model: Any = None,
    ) -> None:
        self.min_cluster_size = min_cluster_size
        self.auto_params = auto_params
        self._umap_model = umap_model
        self._hdbscan_model = hdbscan_model

    def detect(
        self,
        incident_ids: list[str],
        vectors: list[list[float]],
        metadata_list: list[dict[str, Any]],
        top_n: int | None = None,
    ) -> AnomalyDetectionResult:
        """Run anomaly detection on a set of incident vectors.

        Args:
            incident_ids: IDs aligned with ``vectors`` and ``metadata_list``.
            vectors: Dense float embedding vectors (N x D).
            metadata_list: VectorMetadata dicts, one per incident.
            top_n: If set, cap the returned anomalies list at this length.

        Returns:
            AnomalyDetectionResult with ranked anomalies.
        """
        n = len(incident_ids)

        if n < 2:
            logger.warning("AnomalyDetector: need >=2 incidents; got %d", n)
            return AnomalyDetectionResult(
                total_incidents=n,
                n_clusters=0,
                n_anomalies=0,
                anomaly_ratio=0.0,
                anomalies=[],
            )

        X = np.array(vectors, dtype=np.float32)
        effective_min = self._effective_min_cluster_size(n)

        reduced = self._reduce(X)
        labels, outlier_scores = self._cluster(reduced, effective_min)

        unique_clusters = set(labels.tolist()) - {-1}
        noise_indices = [i for i, lbl in enumerate(labels) if lbl == -1]

        anomalies = [
            AnomalyResult(
                incident_id=incident_ids[i],
                outlier_score=round(float(outlier_scores[i]), 4),
                severity=metadata_list[i].get("severity", "Unknown"),
                surgery_type=metadata_list[i].get("surgery_type", "Unknown"),
                incident_type=metadata_list[i].get("incident_type", []),
                root_cause=metadata_list[i].get("root_cause", "")[:200],
                source=metadata_list[i].get("source", "unknown"),
            )
            for i in noise_indices
        ]

        # Sort by outlier_score descending (most anomalous first)
        anomalies.sort(key=lambda a: a.outlier_score, reverse=True)

        if top_n is not None:
            anomalies = anomalies[:top_n]

        n_anomalies = len(noise_indices)
        logger.info(
            "AnomalyDetector: %d/%d incidents anomalous (%.1f%%), %d clusters",
            n_anomalies, n, 100 * n_anomalies / n if n else 0, len(unique_clusters),
        )

        return AnomalyDetectionResult(
            total_incidents=n,
            n_clusters=len(unique_clusters),
            n_anomalies=n_anomalies,
            anomaly_ratio=round(n_anomalies / n, 4) if n else 0.0,
            anomalies=anomalies,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _effective_min_cluster_size(self, n: int) -> int:
        if self.auto_params:
            return max(3, int(math.sqrt(n)))
        return max(2, min(self.min_cluster_size, n // 2))

    def _reduce(self, X: np.ndarray) -> np.ndarray:
        if self._umap_model is not None:
            return self._umap_model.fit_transform(X)
        if X.shape[0] < 3:
            return X

        import umap as umap_lib

        n_neighbors = max(2, min(15, X.shape[0] - 1))
        init = "random" if X.shape[0] < 50 else "spectral"
        n_components = max(1, min(10, X.shape[0] - 2, X.shape[1]))
        return umap_lib.UMAP(
            n_components=n_components,
            n_neighbors=n_neighbors,
            min_dist=0.1,
            random_state=42,
            init=init,
        ).fit_transform(X)

    def _cluster(
        self, X: np.ndarray, min_cluster_size: int
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return (labels, outlier_scores).  Both are length-N arrays."""
        if self._hdbscan_model is not None:
            labels = np.array(self._hdbscan_model.fit_predict(X))
            scores = getattr(self._hdbscan_model, "outlier_scores_", None)
            if scores is None:
                scores = np.zeros(len(labels), dtype=np.float32)
            return labels, np.array(scores, dtype=np.float32)

        import hdbscan

        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=min(min_cluster_size, max(2, X.shape[0] // 2)),
            min_samples=max(1, min_cluster_size - 1),
            prediction_data=True,
        )
        labels = clusterer.fit_predict(X)
        outlier_scores = getattr(clusterer, "outlier_scores_", np.zeros(len(labels)))
        return np.array(labels), np.array(outlier_scores, dtype=np.float32)
