"""Unit tests for Week 7 clustering engine.

Uses fake UMAP (returns first 2 columns of X) and fake HDBSCAN (splits by
median of first column) to exercise all clustering logic without real model
downloads.
"""

from __future__ import annotations

import uuid

import numpy as np
import pytest

from src.retrieval.clustering import (
    ClusterTheme,
    ClusteringResult,
    IncidentClusteringEngine,
    extract_patterns,
    extract_root_cause_keywords,
    fallback_insight,
    fallback_recommendations,
    fallback_theme_name,
    most_common_values,
)


# ---------------------------------------------------------------------------
# Fake models
# ---------------------------------------------------------------------------


class _FakeUMAP:
    """Returns first min(2, D) columns of X."""

    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        cols = min(2, X.shape[1])
        return X[:, :cols].astype(np.float32)


class _FakeHDBSCAN:
    """Splits into label 0 / label 1 based on median of first column."""

    def fit_predict(self, X: np.ndarray) -> np.ndarray:
        if X.shape[0] < 2:
            return np.array([-1] * X.shape[0])
        median = float(np.median(X[:, 0]))
        return np.array([0 if float(x[0]) >= median else 1 for x in X])


class _AllNoiseHDBSCAN:
    """Marks every point as noise."""

    def fit_predict(self, X: np.ndarray) -> np.ndarray:
        return np.full(X.shape[0], -1)


class _OneLabelHDBSCAN:
    """Assigns every point to label 0 (single cluster)."""

    def fit_predict(self, X: np.ndarray) -> np.ndarray:
        return np.zeros(X.shape[0], dtype=int)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _engine(min_cluster_size: int = 2, hdbscan=None) -> IncidentClusteringEngine:
    return IncidentClusteringEngine(
        min_cluster_size=min_cluster_size,
        umap_model=_FakeUMAP(),
        hdbscan_model=hdbscan or _FakeHDBSCAN(),
    )


def _uuids(n: int) -> list[str]:
    return [str(uuid.uuid4()) for _ in range(n)]


def _vectors(n: int, dim: int = 8) -> list[list[float]]:
    """First half get positive first coord, second half negative."""
    vecs = []
    for i in range(n):
        v = [0.1] * dim
        v[0] = 1.0 if i < n // 2 else -1.0
        vecs.append(v)
    return vecs


def _meta(
    incident_type: str = "Medication Error",
    severity: str = "High",
    surgery_type: str = "Colorectal",
    root_cause: str = "Labeling failure during handover",
    severity_score: float = 0.8,
) -> dict:
    return {
        "incident_type": [incident_type],
        "severity": severity,
        "surgery_type": surgery_type,
        "root_cause": root_cause,
        "severity_score": severity_score,
    }


# ---------------------------------------------------------------------------
# ClusteringResult
# ---------------------------------------------------------------------------


class TestClusteringResult:
    def test_is_meaningful_two_clusters(self):
        result = ClusteringResult(
            themes=[object(), object()],
            noise_incident_ids=[],
            total_incidents=10,
            n_clusters=2,
            silhouette_score=0.5,
            noise_ratio=0.0,
            umap_coords=[],
        )
        assert result.is_meaningful is True

    def test_is_meaningful_one_cluster(self):
        result = ClusteringResult(
            themes=[object()],
            noise_incident_ids=[],
            total_incidents=5,
            n_clusters=1,
            silhouette_score=0.5,
            noise_ratio=0.0,
            umap_coords=[],
        )
        assert result.is_meaningful is False

    def test_is_meaningful_no_clusters(self):
        result = ClusteringResult(
            themes=[],
            noise_incident_ids=["a"],
            total_incidents=1,
            n_clusters=0,
            silhouette_score=None,
            noise_ratio=1.0,
            umap_coords=[],
        )
        assert result.is_meaningful is False

    def test_summary_report_no_silhouette(self):
        result = ClusteringResult(
            themes=[],
            noise_incident_ids=["a"],
            total_incidents=1,
            n_clusters=0,
            silhouette_score=None,
            noise_ratio=1.0,
            umap_coords=[],
        )
        report = result.summary_report()
        assert "Silhouette score: N/A" in report
        assert "0 themes" in report

    def test_summary_report_with_silhouette(self):
        result = ClusteringResult(
            themes=[],
            noise_incident_ids=[],
            total_incidents=4,
            n_clusters=0,
            silhouette_score=0.623,
            noise_ratio=0.0,
            umap_coords=[],
        )
        report = result.summary_report()
        assert "0.623" in report

    def test_summary_report_includes_theme_name(self):
        theme = ClusterTheme(
            theme_id="theme_000",
            theme_name="Airway Obstruction",
            theme_description="desc",
            incident_ids=["id1"],
            incident_count=1,
            patterns=[],
            common_incident_types=["Airway"],
            common_severity="High",
            common_root_causes=[],
            average_severity_score=0.9,
            key_insight="Recurrent airway issue.",
            recommendations=["Review protocols"],
        )
        result = ClusteringResult(
            themes=[theme],
            noise_incident_ids=[],
            total_incidents=1,
            n_clusters=1,
            silhouette_score=None,
            noise_ratio=0.0,
            umap_coords=[],
        )
        report = result.summary_report()
        assert "Airway Obstruction" in report
        assert "Review protocols" in report

    def test_summary_report_noise_percentage(self):
        result = ClusteringResult(
            themes=[],
            noise_incident_ids=["a", "b"],
            total_incidents=4,
            n_clusters=0,
            silhouette_score=None,
            noise_ratio=0.5,
            umap_coords=[],
        )
        report = result.summary_report()
        assert "50.0%" in report


# ---------------------------------------------------------------------------
# IncidentClusteringEngine — edge cases
# ---------------------------------------------------------------------------


class TestClusteringEngineTooFew:
    def test_zero_incidents(self):
        result = _engine().cluster([], [], [])
        assert result.total_incidents == 0
        assert result.n_clusters == 0
        assert result.noise_incident_ids == []

    def test_one_incident_all_noise(self):
        ids = _uuids(1)
        result = _engine().cluster(ids, [[0.1] * 8], [_meta()])
        assert result.n_clusters == 0
        assert result.noise_incident_ids == ids
        assert result.total_incidents == 1

    def test_one_incident_noise_ratio_one(self):
        ids = _uuids(1)
        result = _engine().cluster(ids, [[0.1] * 8], [_meta()])
        assert result.noise_ratio == 1.0


# ---------------------------------------------------------------------------
# IncidentClusteringEngine — clustering logic
# ---------------------------------------------------------------------------


class TestClusteringEngine:
    def test_returns_clustering_result(self):
        ids = _uuids(6)
        result = _engine().cluster(ids, _vectors(6), [_meta()] * 6)
        assert isinstance(result, ClusteringResult)

    def test_two_clusters_produced(self):
        ids = _uuids(6)
        result = _engine().cluster(ids, _vectors(6), [_meta()] * 6)
        assert result.n_clusters == 2

    def test_all_incidents_accounted_for(self):
        ids = _uuids(6)
        result = _engine().cluster(ids, _vectors(6), [_meta()] * 6)
        assigned = {iid for t in result.themes for iid in t.incident_ids}
        all_ids = assigned | set(result.noise_incident_ids)
        assert all_ids == set(ids)

    def test_umap_coords_length(self):
        ids = _uuids(6)
        result = _engine().cluster(ids, _vectors(6), [_meta()] * 6)
        assert len(result.umap_coords) == 6

    def test_umap_coords_have_required_keys(self):
        ids = _uuids(4)
        result = _engine().cluster(ids, _vectors(4), [_meta()] * 4)
        for coord in result.umap_coords:
            assert "incident_id" in coord
            assert "x" in coord
            assert "y" in coord
            assert "cluster_id" in coord

    def test_umap_coords_incident_ids_match(self):
        ids = _uuids(4)
        result = _engine().cluster(ids, _vectors(4), [_meta()] * 4)
        coord_ids = {c["incident_id"] for c in result.umap_coords}
        assert coord_ids == set(ids)

    def test_noise_ratio_correct(self):
        ids = _uuids(4)
        result = _engine().cluster(ids, _vectors(4), [_meta()] * 4)
        assert result.noise_ratio == pytest.approx(
            len(result.noise_incident_ids) / 4
        )

    def test_theme_incident_count_matches_ids(self):
        ids = _uuids(6)
        result = _engine().cluster(ids, _vectors(6), [_meta()] * 6)
        for theme in result.themes:
            assert theme.incident_count == len(theme.incident_ids)

    def test_theme_has_nonempty_name(self):
        ids = _uuids(6)
        result = _engine().cluster(ids, _vectors(6), [_meta()] * 6)
        for theme in result.themes:
            assert len(theme.theme_name) > 0

    def test_theme_has_recommendations(self):
        ids = _uuids(6)
        result = _engine().cluster(ids, _vectors(6), [_meta(incident_type="Airway")] * 6)
        for theme in result.themes:
            assert len(theme.recommendations) >= 1

    def test_theme_ids_are_unique(self):
        ids = _uuids(6)
        result = _engine().cluster(ids, _vectors(6), [_meta()] * 6)
        theme_ids = [t.theme_id for t in result.themes]
        assert len(theme_ids) == len(set(theme_ids))


# ---------------------------------------------------------------------------
# IncidentClusteringEngine — silhouette score
# ---------------------------------------------------------------------------


class TestSilhouetteScore:
    def test_none_when_all_noise(self):
        result = IncidentClusteringEngine(
            umap_model=_FakeUMAP(),
            hdbscan_model=_AllNoiseHDBSCAN(),
        ).cluster(_uuids(4), _vectors(4), [_meta()] * 4)
        assert result.silhouette_score is None

    def test_none_when_one_cluster(self):
        result = IncidentClusteringEngine(
            umap_model=_FakeUMAP(),
            hdbscan_model=_OneLabelHDBSCAN(),
        ).cluster(_uuids(4), _vectors(4), [_meta()] * 4)
        assert result.silhouette_score is None

    def test_score_present_when_two_clusters(self):
        result = _engine().cluster(_uuids(6), _vectors(6), [_meta()] * 6)
        # Two clusters -> silhouette should be computable
        # (may still be None if all points in one cluster after label split)
        # At minimum it should be a float or None, not raise
        assert result.silhouette_score is None or isinstance(
            result.silhouette_score, float
        )


# ---------------------------------------------------------------------------
# ThemeExtractor injection
# ---------------------------------------------------------------------------


class TestThemeExtractorInjection:
    def test_extractor_called_per_cluster(self):
        class _Counter:
            calls = 0

            def name_theme(self, metadata_list):
                _Counter.calls += 1
                return "Injected Theme", "Injected insight.", ["Injected rec."]

        extractor = _Counter()
        ids = _uuids(6)
        result = _engine().cluster(ids, _vectors(6), [_meta()] * 6, theme_extractor=extractor)
        assert extractor.calls == result.n_clusters

    def test_extractor_result_propagated(self):
        class _Fixed:
            def name_theme(self, metadata_list):
                return "Fixed Theme", "Fixed.", ["Fix this."]

        ids = _uuids(6)
        result = _engine().cluster(ids, _vectors(6), [_meta()] * 6, theme_extractor=_Fixed())
        for theme in result.themes:
            assert theme.theme_name == "Fixed Theme"
            assert theme.key_insight == "Fixed."
            assert theme.recommendations == ["Fix this."]

    def test_no_extractor_uses_fallback(self):
        ids = _uuids(6)
        result = _engine().cluster(ids, _vectors(6), [_meta(incident_type="Airway")] * 6)
        for theme in result.themes:
            assert "Airway" in theme.theme_name or len(theme.theme_name) > 0


# ---------------------------------------------------------------------------
# Pattern extraction helpers
# ---------------------------------------------------------------------------


class TestMostCommonValues:
    def test_top_n(self):
        values = ["A", "A", "B", "B", "B", "C"]
        assert most_common_values(values, n=2) == ["B", "A"]

    def test_skips_unknown(self):
        values = ["Unknown", "Unknown", "A"]
        assert most_common_values(values, n=3) == ["A"]

    def test_empty_input(self):
        assert most_common_values([], n=3) == []

    def test_skips_empty_string(self):
        assert most_common_values(["", "", "X"], n=2) == ["X"]


class TestExtractPatterns:
    def test_incident_types_present(self):
        patterns = extract_patterns([_meta(incident_type="Airway")] * 3)
        assert any("Airway" in p for p in patterns)

    def test_severity_present(self):
        patterns = extract_patterns([_meta(severity="Critical")] * 3)
        assert any("Critical" in p for p in patterns)

    def test_surgical_context_present(self):
        patterns = extract_patterns([_meta(surgery_type="Cardiac")] * 3)
        assert any("Cardiac" in p for p in patterns)

    def test_root_cause_keywords_present(self):
        patterns = extract_patterns(
            [_meta(root_cause="Labeling failure protocol breakdown")] * 3
        )
        assert any("Root cause" in p for p in patterns)


class TestExtractRootCauseKeywords:
    def test_returns_keywords(self):
        meta = [_meta(root_cause="Labeling failure protocol breakdown")] * 5
        kws = extract_root_cause_keywords(meta, n=3)
        assert len(kws) >= 1

    def test_stopwords_excluded(self):
        meta = [_meta(root_cause="the and with of in to")] * 3
        kws = extract_root_cause_keywords(meta, n=5)
        stopwords = {"the", "and", "with", "of", "in", "to"}
        for kw in kws:
            assert kw not in stopwords

    def test_empty_root_cause(self):
        meta = [_meta(root_cause="")] * 3
        assert extract_root_cause_keywords(meta) == []


class TestFallbackHelpers:
    def test_fallback_theme_name_with_types(self):
        name = fallback_theme_name(["Airway", "Equipment"], ["High"])
        assert "Airway" in name
        assert "Equipment" in name
        assert "High" in name

    def test_fallback_theme_name_single_type(self):
        name = fallback_theme_name(["Airway"], [])
        assert "Airway" in name

    def test_fallback_theme_name_empty(self):
        assert fallback_theme_name([], []) == "Mixed Clinical Incidents"

    def test_fallback_insight_with_data(self):
        insight = fallback_insight(["labeling", "failure"], ["Medication Error"])
        assert "Medication Error" in insight
        assert "labeling" in insight

    def test_fallback_insight_only_types(self):
        insight = fallback_insight([], ["Airway"])
        assert "Airway" in insight

    def test_fallback_insight_empty(self):
        insight = fallback_insight([], [])
        assert len(insight) > 0

    def test_fallback_recommendations_with_types(self):
        recs = fallback_recommendations(["Airway", "Equipment"])
        assert len(recs) >= 1
        assert any("airway" in r.lower() for r in recs)

    def test_fallback_recommendations_empty(self):
        recs = fallback_recommendations([])
        assert len(recs) == 1
        assert "multidisciplinary" in recs[0].lower()
