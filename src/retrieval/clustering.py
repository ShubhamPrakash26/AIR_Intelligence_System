"""HDBSCAN + UMAP theme clustering for clinical incident vectors.

Pipeline:
  Stored vectors (Qdrant) -> QdrantHandler.scroll_all()
    -> UMAP dimensionality reduction (nD for clustering, 2D for visualisation)
    -> HDBSCAN density clustering
    -> Pattern extraction per cluster (incident types, severity, root cause)
    -> Optional LLM-assisted theme naming via ThemeExtractor
    -> ClusteringResult with ClusterTheme list, quality metrics, UMAP coords

Testing: inject ``umap_model`` and ``hdbscan_model`` to avoid real model
downloads.  Both need ``fit_transform(X)`` / ``fit_predict(X)`` respectively.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from src.utils.logger import get_logger

logger = get_logger(__name__)

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "in", "to", "for", "with",
    "during", "was", "is", "are", "were", "by", "on", "at", "that",
    "this", "from", "be", "not", "it", "as", "due", "no", "into",
    "also", "which", "when", "had", "has", "have", "been",
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ClusterTheme:
    """One clinically meaningful theme identified by HDBSCAN."""

    theme_id: str
    theme_name: str
    theme_description: str
    incident_ids: list[str]
    incident_count: int
    patterns: list[str]
    common_incident_types: list[str]
    common_severity: str
    common_root_causes: list[str]
    average_severity_score: float
    key_insight: str
    recommendations: list[str]
    umap_x: list[float] = field(default_factory=list)
    umap_y: list[float] = field(default_factory=list)


@dataclass
class ClusteringResult:
    """Full output of a single clustering run."""

    themes: list[ClusterTheme]
    noise_incident_ids: list[str]
    total_incidents: int
    n_clusters: int
    silhouette_score: float | None
    noise_ratio: float
    umap_coords: list[dict[str, Any]]  # [{incident_id, x, y, cluster_id}]

    @property
    def is_meaningful(self) -> bool:
        """True when >=2 clusters were identified."""
        return self.n_clusters >= 2

    def summary_report(self) -> str:
        """Human-readable plain-text clustering summary."""
        sil = f"{self.silhouette_score:.3f}" if self.silhouette_score is not None else "N/A"
        lines: list[str] = [
            f"Clustering Report -- {self.n_clusters} themes, {self.total_incidents} incidents",
            f"Noise: {len(self.noise_incident_ids)} ({self.noise_ratio:.1%})",
            f"Silhouette score: {sil}",
            "",
        ]
        for theme in self.themes:
            lines += [
                f"[{theme.theme_id}] {theme.theme_name}",
                f"  Incidents: {theme.incident_count}",
                f"  Types: {', '.join(theme.common_incident_types) or 'Mixed'}",
                f"  Severity: {theme.common_severity}  (avg score {theme.average_severity_score:.2f})",
                f"  Key insight: {theme.key_insight}",
            ]
            for rec in theme.recommendations[:2]:
                lines.append(f"  -> {rec}")
            lines.append("")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Clustering engine
# ---------------------------------------------------------------------------


class IncidentClusteringEngine:
    """Cluster clinical incident vectors using UMAP + HDBSCAN.

    Args:
        min_cluster_size: Minimum incidents per HDBSCAN cluster.
        min_samples: HDBSCAN min_samples (controls noise sensitivity).
        n_umap_components: Dimensions for HDBSCAN input (not 2D viz).
        umap_random_state: Reproducibility seed for UMAP.
        umap_model: Optional injectable UMAP-like object (``fit_transform``).
        hdbscan_model: Optional injectable HDBSCAN-like object (``fit_predict``).
    """

    def __init__(
        self,
        min_cluster_size: int = 3,
        min_samples: int = 2,
        n_umap_components: int = 10,
        umap_random_state: int = 42,
        umap_model: Any = None,
        hdbscan_model: Any = None,
    ) -> None:
        self.min_cluster_size = min_cluster_size
        self.min_samples = min_samples
        self.n_umap_components = n_umap_components
        self.umap_random_state = umap_random_state
        self._umap_model = umap_model
        self._hdbscan_model = hdbscan_model

    def cluster(
        self,
        incident_ids: list[str],
        vectors: list[list[float]],
        metadata_list: list[dict[str, Any]],
        theme_extractor: Any = None,
    ) -> ClusteringResult:
        """Run the full clustering pipeline.

        Args:
            incident_ids: IDs in the same order as ``vectors``.
            vectors: Embedding vectors (N x D).
            metadata_list: VectorMetadata dicts for each incident.
            theme_extractor: Optional ThemeExtractor for LLM-assisted naming.

        Returns:
            ClusteringResult with themes, noise IDs, metrics, and UMAP coords.
        """
        n = len(incident_ids)
        if n < 2:
            logger.warning("Clustering requires >=2 incidents; got %d", n)
            return ClusteringResult(
                themes=[],
                noise_incident_ids=list(incident_ids),
                total_incidents=n,
                n_clusters=0,
                silhouette_score=None,
                noise_ratio=1.0 if n else 0.0,
                umap_coords=[],
            )

        X = np.array(vectors, dtype=np.float32)

        reduced = self._reduce_dimensions(X)
        reduced_2d = self._reduce_to_2d(X)
        labels = self._run_hdbscan(reduced)

        umap_coords = [
            {
                "incident_id": incident_ids[i],
                "x": float(reduced_2d[i, 0]),
                "y": float(reduced_2d[i, 1]),
                "cluster_id": int(labels[i]),
            }
            for i in range(n)
        ]

        silhouette = self._compute_silhouette(reduced, labels)
        unique_labels = sorted(set(labels.tolist()) - {-1})
        noise_ids = [incident_ids[i] for i, lbl in enumerate(labels) if lbl == -1]

        themes: list[ClusterTheme] = []
        for label in unique_labels:
            indices = [i for i, lbl in enumerate(labels) if lbl == label]
            themes.append(
                self._build_theme(
                    label=label,
                    incident_ids=[incident_ids[i] for i in indices],
                    metadata_list=[metadata_list[i] for i in indices],
                    umap_x=[float(reduced_2d[i, 0]) for i in indices],
                    umap_y=[float(reduced_2d[i, 1]) for i in indices],
                    theme_extractor=theme_extractor,
                )
            )

        noise_ratio = len(noise_ids) / n
        logger.info(
            "Clustering complete: %d themes, %d noise, silhouette=%s",
            len(themes),
            len(noise_ids),
            f"{silhouette:.3f}" if silhouette is not None else "N/A",
        )

        return ClusteringResult(
            themes=themes,
            noise_incident_ids=noise_ids,
            total_incidents=n,
            n_clusters=len(themes),
            silhouette_score=silhouette,
            noise_ratio=noise_ratio,
            umap_coords=umap_coords,
        )

    # ------------------------------------------------------------------
    # Pipeline steps
    # ------------------------------------------------------------------

    def _reduce_dimensions(self, X: np.ndarray) -> np.ndarray:
        """UMAP reduction to n_umap_components for HDBSCAN input.

        Small-sample constraints enforced here:
        - n < 3: UMAP needs n_neighbors >= 2; skip and return raw vectors.
        - n_components capped at n-2: UMAP spectral init needs n_components+1
          eigenvectors, so k must be < n_samples to avoid scipy eigsh failure.
        - init="random" for n < 50: spectral init is an optimisation that
          adds no value on small datasets and triggers the eigsh error.
        """
        if self._umap_model is not None:
            return self._umap_model.fit_transform(X)

        if X.shape[0] < 3:
            return X

        import umap as umap_lib

        n_components = max(1, min(self.n_umap_components, X.shape[0] - 2, X.shape[1]))
        n_neighbors = max(2, min(15, X.shape[0] - 1))
        init = "random" if X.shape[0] < 50 else "spectral"

        reducer = umap_lib.UMAP(
            n_components=n_components,
            random_state=self.umap_random_state,
            n_neighbors=n_neighbors,
            min_dist=0.1,
            init=init,
        )
        return reducer.fit_transform(X)

    def _reduce_to_2d(self, X: np.ndarray) -> np.ndarray:
        """Separate 2D UMAP pass for visualisation coordinates.

        When a fake ``umap_model`` is injected (test mode), returns the first
        two columns of X to avoid importing the real library.
        """
        if X.shape[0] < 3:
            return np.zeros((X.shape[0], 2), dtype=np.float32)

        if self._umap_model is not None:
            cols = min(2, X.shape[1])
            out = np.zeros((X.shape[0], 2), dtype=np.float32)
            out[:, :cols] = X[:, :cols]
            return out

        import umap as umap_lib

        n_neighbors = max(2, min(15, X.shape[0] - 1))
        init = "random" if X.shape[0] < 50 else "spectral"

        reducer = umap_lib.UMAP(
            n_components=2,
            random_state=self.umap_random_state,
            n_neighbors=n_neighbors,
            min_dist=0.1,
            init=init,
        )
        return reducer.fit_transform(X)

    def _run_hdbscan(self, X: np.ndarray) -> np.ndarray:
        """HDBSCAN clustering. Returns integer label array (-1 == noise)."""
        if self._hdbscan_model is not None:
            return np.array(self._hdbscan_model.fit_predict(X))

        import hdbscan

        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=min(self.min_cluster_size, max(2, X.shape[0] // 2)),
            min_samples=min(self.min_samples, X.shape[0]),
        )
        return clusterer.fit_predict(X)

    def _compute_silhouette(self, X: np.ndarray, labels: np.ndarray) -> float | None:
        """Silhouette score for non-noise points; None when <2 clusters."""
        unique_non_noise = set(labels.tolist()) - {-1}
        if len(unique_non_noise) < 2:
            return None
        mask = labels != -1
        if mask.sum() < 2:
            return None
        from sklearn.metrics import silhouette_score

        try:
            return float(silhouette_score(X[mask], labels[mask]))
        except Exception:
            return None

    def _build_theme(
        self,
        label: int,
        incident_ids: list[str],
        metadata_list: list[dict[str, Any]],
        umap_x: list[float],
        umap_y: list[float],
        theme_extractor: Any,
    ) -> ClusterTheme:
        patterns = extract_patterns(metadata_list)
        common_types = most_common_values(
            [t for m in metadata_list for t in m.get("incident_type", [])], n=3
        )
        common_severity = most_common_values(
            [m.get("severity", "Unknown") for m in metadata_list], n=2
        )
        common_roots = extract_root_cause_keywords(metadata_list, n=5)
        avg_score = float(
            np.mean([m.get("severity_score", 0.0) for m in metadata_list])
        )

        if theme_extractor is not None:
            theme_name, key_insight, recommendations = theme_extractor.name_theme(
                metadata_list
            )
        else:
            theme_name = fallback_theme_name(common_types, common_severity)
            key_insight = fallback_insight(common_roots, common_types)
            recommendations = fallback_recommendations(common_types)

        return ClusterTheme(
            theme_id=f"theme_{label:03d}",
            theme_name=theme_name,
            theme_description=(
                f"{len(incident_ids)} incidents sharing patterns in "
                f"{', '.join(common_types[:2]) or 'clinical context'}"
            ),
            incident_ids=incident_ids,
            incident_count=len(incident_ids),
            patterns=patterns,
            common_incident_types=common_types,
            common_severity=common_severity[0] if common_severity else "Unknown",
            common_root_causes=common_roots,
            average_severity_score=round(avg_score, 3),
            key_insight=key_insight,
            recommendations=recommendations,
            umap_x=umap_x,
            umap_y=umap_y,
        )


# ---------------------------------------------------------------------------
# Pattern extraction utilities (also imported by ThemeExtractor fallback)
# ---------------------------------------------------------------------------


def most_common_values(values: list[str], n: int = 3) -> list[str]:
    """Return the top-n most frequent non-unknown values."""
    counts = Counter(
        v for v in values if v and v.lower() not in {"unknown", ""}
    )
    return [item for item, _ in counts.most_common(n)]


def extract_patterns(metadata_list: list[dict[str, Any]]) -> list[str]:
    """Summarise recurring metadata patterns across a cluster."""
    patterns: list[str] = []

    top_types = most_common_values(
        [t for m in metadata_list for t in m.get("incident_type", [])], n=3
    )
    if top_types:
        patterns.append(f"Incident types: {', '.join(top_types)}")

    top_sev = most_common_values(
        [m.get("severity", "") for m in metadata_list], n=2
    )
    if top_sev:
        patterns.append(f"Severity: {', '.join(top_sev)}")

    top_surg = most_common_values(
        [m.get("surgery_type", "") for m in metadata_list], n=2
    )
    if top_surg:
        patterns.append(f"Surgical context: {', '.join(top_surg)}")

    rc_words = extract_root_cause_keywords(metadata_list, n=3)
    if rc_words:
        patterns.append(f"Root cause keywords: {', '.join(rc_words)}")

    return patterns


def extract_root_cause_keywords(
    metadata_list: list[dict[str, Any]], n: int = 5
) -> list[str]:
    """Extract the top-n content words from root_cause fields."""
    words: list[str] = []
    for m in metadata_list:
        rc = m.get("root_cause", "")
        if rc:
            words.extend(
                w.lower().strip(".,;:()")
                for w in rc.split()
                if len(w) > 3
                and w.lower().strip(".,;:()") not in _STOPWORDS
            )
    counts = Counter(words)
    return [w for w, _ in counts.most_common(n) if w]


def fallback_theme_name(
    common_types: list[str], common_severity: list[str]
) -> str:
    """Generate a theme name without an LLM."""
    if common_types:
        name = " & ".join(common_types[:2])
        if common_severity:
            name += f" ({common_severity[0]})"
        return name
    return "Mixed Clinical Incidents"


def fallback_insight(
    root_cause_keywords: list[str], common_types: list[str]
) -> str:
    """Generate a key insight string without an LLM."""
    if root_cause_keywords and common_types:
        return (
            f"Recurring {', '.join(common_types[:2])} incidents sharing root causes "
            f"involving {', '.join(root_cause_keywords[:3])}."
        )
    if common_types:
        return (
            f"Cluster of {', '.join(common_types[:2])} incidents with shared "
            f"contextual factors."
        )
    return "Group of incidents sharing similar clinical characteristics."


def fallback_recommendations(common_types: list[str]) -> list[str]:
    """Generate basic recommendations without an LLM."""
    recs = [
        f"Review and audit {t.lower()} protocols across affected cases."
        for t in common_types[:3]
    ]
    return recs or ["Conduct multidisciplinary review of clustered incidents."]
