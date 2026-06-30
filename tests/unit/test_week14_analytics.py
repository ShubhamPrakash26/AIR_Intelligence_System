"""Unit tests for Week 14: Anomaly Detection & Pattern Analysis.

Covers:
  - AnomalyDetector (with injected fake UMAP + HDBSCAN models)
  - AnomalyResult / AnomalyDetectionResult data classes
  - PatternAnalyzer (pure Python, no ML)
  - PeriodStats + PatternAnalysis data classes
  - IncidentClusteringEngine auto_params flag
  - AnomalyResponse / PatternResponse Pydantic models

No real model downloads, no Qdrant.
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from src.retrieval.anomaly_detector import AnomalyDetector, AnomalyDetectionResult, AnomalyResult
from src.retrieval.pattern_analyzer import PatternAnalyzer, PatternAnalysis, PeriodStats


# ---------------------------------------------------------------------------
# Helpers — fake UMAP + HDBSCAN for injection
# ---------------------------------------------------------------------------


class _IdentityUMAP:
    """Pass-through: returns input unchanged."""
    def fit_transform(self, X):
        return X


class _FakeHDBSCAN:
    """Returns predetermined labels and optional outlier_scores_."""

    def __init__(self, labels, outlier_scores=None):
        self._labels = labels
        self.outlier_scores_ = outlier_scores

    def fit_predict(self, X):
        return np.array(self._labels)


def _meta(
    severity="High",
    surgery="Cardiac",
    types=None,
    root_cause="Root cause text",
    source="test.xlsx",
    source_type="incident_report",
    year=2026,
    month="March",
):
    return {
        "severity": severity,
        "surgery_type": surgery,
        "incident_type": types or ["Airway Event"],
        "root_cause": root_cause,
        "source": source,
        "source_type": source_type,
        "year": year,
        "month": month,
        "severity_score": 0.8,
    }


def _vecs(n, dim=8):
    rng = np.random.default_rng(42)
    return rng.standard_normal((n, dim)).tolist()


# ---------------------------------------------------------------------------
# AnomalyDetector — basic behaviour
# ---------------------------------------------------------------------------


class TestAnomalyDetectorBasic:
    def _detector(self, labels, outlier_scores=None):
        return AnomalyDetector(
            umap_model=_IdentityUMAP(),
            hdbscan_model=_FakeHDBSCAN(labels, outlier_scores),
        )

    def test_returns_detection_result(self):
        ids = ["a", "b", "c", "d"]
        metas = [_meta() for _ in ids]
        result = self._detector([0, 0, -1, -1]).detect(ids, _vecs(4), metas)
        assert isinstance(result, AnomalyDetectionResult)

    def test_noise_count_matches_label_minus_one(self):
        ids = ["a", "b", "c", "d", "e"]
        metas = [_meta() for _ in ids]
        result = self._detector([0, 0, 0, -1, -1]).detect(ids, _vecs(5), metas)
        assert result.n_anomalies == 2

    def test_anomaly_ratio_correct(self):
        ids = ["a", "b", "c", "d"]
        metas = [_meta() for _ in ids]
        result = self._detector([0, 0, -1, -1]).detect(ids, _vecs(4), metas)
        assert result.anomaly_ratio == pytest.approx(0.5)

    def test_cluster_count_excludes_noise(self):
        ids = ["a", "b", "c", "d", "e", "f"]
        metas = [_meta() for _ in ids]
        result = self._detector([0, 0, 1, 1, -1, -1]).detect(ids, _vecs(6), metas)
        assert result.n_clusters == 2

    def test_anomaly_ids_correct(self):
        ids = ["alpha", "beta", "gamma"]
        metas = [_meta() for _ in ids]
        result = self._detector([0, -1, 0]).detect(ids, _vecs(3), metas)
        assert len(result.anomalies) == 1
        assert result.anomalies[0].incident_id == "beta"

    def test_anomaly_metadata_fields(self):
        ids = ["x", "y"]
        metas = [
            _meta(severity="Critical", surgery="Obstetric", types=["Drug Error"]),
            _meta(),
        ]
        result = self._detector([-1, 0]).detect(ids, _vecs(2), metas)
        a = result.anomalies[0]
        assert a.severity == "Critical"
        assert a.surgery_type == "Obstetric"
        assert "Drug Error" in a.incident_type

    def test_reason_field_set(self):
        ids = ["x", "y"]
        metas = [_meta(), _meta()]
        result = self._detector([-1, 0]).detect(ids, _vecs(2), metas)
        assert len(result.anomalies[0].reason) > 0

    def test_outlier_scores_used_when_available(self):
        ids = ["a", "b", "c"]
        metas = [_meta() for _ in ids]
        scores = np.array([0.9, 0.1, 0.7], dtype=np.float32)
        result = self._detector([-1, 0, -1], outlier_scores=scores).detect(
            ids, _vecs(3), metas
        )
        # Most anomalous (score=0.9) should come first
        assert result.anomalies[0].outlier_score == pytest.approx(0.9, abs=1e-3)

    def test_top_n_caps_results(self):
        ids = [str(i) for i in range(10)]
        metas = [_meta() for _ in ids]
        labels = [-1] * 10
        result = self._detector(labels).detect(ids, _vecs(10), metas, top_n=3)
        assert len(result.anomalies) == 3

    def test_no_anomalies_when_all_clustered(self):
        ids = ["a", "b", "c"]
        metas = [_meta() for _ in ids]
        result = self._detector([0, 0, 1]).detect(ids, _vecs(3), metas)
        assert result.n_anomalies == 0
        assert result.anomalies == []

    def test_too_few_incidents_returns_empty(self):
        result = AnomalyDetector().detect(["only"], _vecs(1), [_meta()])
        assert result.n_anomalies == 0
        assert result.total_incidents == 1

    def test_empty_input_returns_empty(self):
        result = AnomalyDetector().detect([], [], [])
        assert result.total_incidents == 0


# ---------------------------------------------------------------------------
# AnomalyDetector — auto_params
# ---------------------------------------------------------------------------


class TestAnomalyDetectorAutoParams:
    def test_auto_params_uses_sqrt_n(self):
        n = 25
        detector = AnomalyDetector(auto_params=True)
        effective = detector._effective_min_cluster_size(n)
        assert effective == max(3, int(math.sqrt(n)))

    def test_auto_params_minimum_3(self):
        detector = AnomalyDetector(auto_params=True)
        assert detector._effective_min_cluster_size(4) >= 3

    def test_manual_params_respected(self):
        detector = AnomalyDetector(min_cluster_size=7, auto_params=False)
        assert detector._effective_min_cluster_size(100) == 7


# ---------------------------------------------------------------------------
# PatternAnalyzer — basic behaviour
# ---------------------------------------------------------------------------


def _record(year, month, severity="High", types=None, source_type="incident_report"):
    return {
        "incident_id": f"id-{year}-{month}",
        "vector": [],
        "metadata": _meta(
            severity=severity,
            types=types or ["Airway Event"],
            year=year,
            month=month,
            source_type=source_type,
        ),
    }


class TestPatternAnalyzerBasic:
    def _analyzer(self):
        return PatternAnalyzer(exclude_literature=True)

    def test_returns_pattern_analysis(self):
        records = [_record(2026, "March")]
        result = self._analyzer().analyze(records)
        assert isinstance(result, PatternAnalysis)

    def test_total_incidents_counts_incident_reports_only(self):
        records = [
            _record(2026, "March"),
            _record(2026, "April"),
            _record(2026, "March", source_type="literature"),
        ]
        result = self._analyzer().analyze(records)
        assert result.total_incidents == 2

    def test_literature_excluded(self):
        records = [_record(2026, "March", source_type="guideline")]
        result = self._analyzer().analyze(records)
        assert result.total_incidents == 0

    def test_empty_records_returns_insufficient_data(self):
        result = self._analyzer().analyze([])
        assert result.trend_direction == "insufficient_data"
        assert result.total_incidents == 0

    def test_single_period_insufficient_trend(self):
        records = [_record(2026, "March"), _record(2026, "March")]
        result = self._analyzer().analyze(records)
        assert result.trend_direction == "insufficient_data"

    def test_periods_sorted_chronologically(self):
        records = [
            _record(2026, "June"),
            _record(2026, "March"),
            _record(2026, "April"),
        ]
        result = self._analyzer().analyze(records)
        years = [p.year for p in result.periods]
        months = [p.month for p in result.periods]
        assert months == ["March", "April", "June"]

    def test_period_count_correct(self):
        records = [_record(2026, "March"), _record(2026, "March"), _record(2026, "April")]
        result = self._analyzer().analyze(records)
        march = next(p for p in result.periods if p.month == "March")
        assert march.count == 2

    def test_dominant_types_populated(self):
        records = [
            _record(2026, "March", types=["Airway Event"]),
            _record(2026, "March", types=["Airway Event"]),
            _record(2026, "March", types=["Drug Error"]),
        ]
        result = self._analyzer().analyze(records)
        assert "Airway Event" in result.dominant_incident_types

    def test_severity_distribution_in_period(self):
        records = [
            _record(2026, "March", severity="High"),
            _record(2026, "March", severity="Low"),
        ]
        result = self._analyzer().analyze(records)
        march = result.periods[0]
        assert "High" in march.severity_distribution
        assert "Low" in march.severity_distribution

    def test_insight_is_non_empty_string(self):
        records = [_record(2026, "March"), _record(2026, "April")]
        result = self._analyzer().analyze(records)
        assert isinstance(result.insight, str)
        assert len(result.insight) > 0


# ---------------------------------------------------------------------------
# PatternAnalyzer — trend detection
# ---------------------------------------------------------------------------


class TestTrendDetection:
    def _analyzer(self):
        return PatternAnalyzer(exclude_literature=True)

    def _build(self, counts_by_period):
        records = []
        months = ["January", "February", "March", "April", "May", "June",
                  "July", "August", "September", "October", "November", "December"]
        for i, (count, (year, month)) in enumerate(counts_by_period):
            for _ in range(count):
                records.append(_record(year, month))
        return records

    def test_increasing_trend(self):
        records = (
            [_record(2026, "January")] * 1
            + [_record(2026, "February")] * 2
            + [_record(2026, "March")] * 4
            + [_record(2026, "April")] * 6
        )
        result = self._analyzer().analyze(records)
        assert result.trend_direction == "increasing"

    def test_decreasing_trend(self):
        records = (
            [_record(2026, "January")] * 6
            + [_record(2026, "February")] * 4
            + [_record(2026, "March")] * 2
            + [_record(2026, "April")] * 1
        )
        result = self._analyzer().analyze(records)
        assert result.trend_direction == "decreasing"

    def test_stable_trend(self):
        records = (
            [_record(2026, "January")] * 3
            + [_record(2026, "February")] * 3
            + [_record(2026, "March")] * 3
        )
        result = self._analyzer().analyze(records)
        assert result.trend_direction == "stable"

    def test_rate_change_pct_calculated(self):
        records = [_record(2026, "January")] * 2 + [_record(2026, "February")] * 4
        result = self._analyzer().analyze(records)
        feb = next(p for p in result.periods if p.month == "February")
        assert feb.rate_change_pct == pytest.approx(100.0)

    def test_first_period_no_rate_change(self):
        records = [_record(2026, "January")] * 2 + [_record(2026, "February")] * 3
        result = self._analyzer().analyze(records)
        jan = result.periods[0]
        assert jan.rate_change_pct is None

    def test_acceleration_detected(self):
        # counts accelerating: 1, 2, 4, 8
        records = (
            [_record(2026, "January")] * 1
            + [_record(2026, "February")] * 2
            + [_record(2026, "March")] * 4
            + [_record(2026, "April")] * 8
        )
        result = self._analyzer().analyze(records)
        assert result.acceleration == "accelerating"

    def test_insufficient_data_for_acceleration(self):
        records = [_record(2026, "January")] * 2 + [_record(2026, "February")] * 3
        result = self._analyzer().analyze(records)
        assert result.acceleration == "insufficient_data"


# ---------------------------------------------------------------------------
# PatternAnalyzer — severity trend
# ---------------------------------------------------------------------------


class TestSeverityTrend:
    def _analyzer(self):
        return PatternAnalyzer(exclude_literature=True)

    def test_worsening_severity_trend(self):
        records = (
            [_record(2026, "January", severity="Low")] * 3
            + [_record(2026, "February", severity="Moderate")] * 3
            + [_record(2026, "March", severity="High")] * 3
        )
        result = self._analyzer().analyze(records)
        assert result.severity_trend == "worsening"

    def test_improving_severity_trend(self):
        records = (
            [_record(2026, "January", severity="High")] * 3
            + [_record(2026, "February", severity="Moderate")] * 3
            + [_record(2026, "March", severity="Low")] * 3
        )
        result = self._analyzer().analyze(records)
        assert result.severity_trend == "improving"


# ---------------------------------------------------------------------------
# IncidentClusteringEngine — auto_params flag
# ---------------------------------------------------------------------------


class TestClusteringAutoParams:
    def test_auto_params_updates_min_cluster_size(self):
        from src.retrieval.clustering import IncidentClusteringEngine
        n = 100
        engine = IncidentClusteringEngine(auto_params=True)

        rng = np.random.default_rng(0)
        X = rng.standard_normal((n, 4)).tolist()
        ids = [str(i) for i in range(n)]
        metas = [_meta() for _ in range(n)]

        class _PassUMAP:
            def fit_transform(self, X):
                return np.array(X)[:, :2]

        class _AllSameCluster:
            def fit_predict(self, X):
                return np.zeros(len(X), dtype=int)

        engine._umap_model = _PassUMAP()
        engine._hdbscan_model = _AllSameCluster()
        engine.cluster(ids, X, metas)
        assert engine.min_cluster_size == max(3, int(math.sqrt(n)))

    def test_auto_params_false_keeps_original(self):
        from src.retrieval.clustering import IncidentClusteringEngine
        engine = IncidentClusteringEngine(min_cluster_size=5, auto_params=False)

        class _PassUMAP:
            def fit_transform(self, X):
                return np.array(X)[:, :2]

        class _AllNoise:
            def fit_predict(self, X):
                return -np.ones(len(X), dtype=int)

        engine._umap_model = _PassUMAP()
        engine._hdbscan_model = _AllNoise()
        n = 16
        engine.cluster(
            [str(i) for i in range(n)],
            np.random.randn(n, 4).tolist(),
            [_meta() for _ in range(n)],
        )
        assert engine.min_cluster_size == 5


# ---------------------------------------------------------------------------
# API Pydantic models
# ---------------------------------------------------------------------------


class TestAnomalyResponseModel:
    def test_valid_model(self):
        from src.api.retrieval import AnomalyResponse, AnomalyHit
        r = AnomalyResponse(
            total_incidents_analysed=10,
            n_clusters_found=2,
            n_anomalies=2,
            anomaly_ratio=0.2,
            anomalies=[
                AnomalyHit(
                    incident_id="abc",
                    outlier_score=0.9,
                    severity="High",
                    surgery_type="Cardiac",
                    incident_type=["Airway Event"],
                    root_cause="Root cause",
                    source="test.xlsx",
                    reason="Unusual pattern",
                )
            ],
        )
        assert r.n_anomalies == 2
        assert r.anomalies[0].outlier_score == pytest.approx(0.9)

    def test_empty_anomalies(self):
        from src.api.retrieval import AnomalyResponse
        r = AnomalyResponse(
            total_incidents_analysed=5,
            n_clusters_found=2,
            n_anomalies=0,
            anomaly_ratio=0.0,
            anomalies=[],
        )
        assert r.anomalies == []


class TestPatternResponseModel:
    def test_valid_model(self):
        from src.api.retrieval import PatternResponse, PeriodStatsResponse
        r = PatternResponse(
            total_incidents=10,
            periods=[
                PeriodStatsResponse(
                    period="2026-March",
                    year=2026,
                    month="March",
                    count=5,
                    dominant_types=["Airway Event"],
                    severity_distribution={"High": 5},
                    rate_change_pct=None,
                    avg_severity_weight=3.0,
                )
            ],
            trend_direction="stable",
            acceleration="insufficient_data",
            dominant_incident_types=["Airway Event"],
            most_volatile_type=None,
            severity_trend="stable",
            insight="Stable trend observed.",
        )
        assert r.trend_direction == "stable"
        assert r.periods[0].count == 5

    def test_nullable_volatile_type(self):
        from src.api.retrieval import PatternResponse
        r = PatternResponse(
            total_incidents=2,
            periods=[],
            trend_direction="insufficient_data",
            acceleration="insufficient_data",
            dominant_incident_types=[],
            most_volatile_type=None,
            severity_trend="insufficient_data",
            insight="No data.",
        )
        assert r.most_volatile_type is None
