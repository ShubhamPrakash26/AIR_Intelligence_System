"""Temporal and categorical pattern analysis for stored clinical incidents.

Analyses the payload records returned by QdrantHandler.scroll_all() to
surface time-based trends, incident type frequency shifts, and severity
distribution changes — without requiring re-embedding or HDBSCAN.

The PatternAnalyzer is intentionally pure Python (no ML dependencies) so it
is fast, always available, and fully testable without Qdrant or a model.

Typical use: POST /retrieval/patterns — returns a PatternAnalysis describing
whether incident rates are rising, falling, or stable over time.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from src.utils.logger import get_logger

logger = get_logger(__name__)

_MONTH_ORDER = {
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12,
}

_SEVERITY_WEIGHT = {
    "None": 0,
    "Low": 1,
    "Moderate": 2,
    "High": 3,
    "Critical": 4,
    "Reference": -1,  # literature — excluded from severity trend
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class PeriodStats:
    """Analytics for a single time period (year + month bucket).

    Attributes:
        period: Human-readable label, e.g. "2026-March".
        year: Calendar year (None if unknown).
        month: Month name (None if unknown).
        count: Total incident records in this period.
        dominant_types: Top-3 incident type labels by frequency.
        severity_distribution: {severity_label: count} mapping.
        rate_change_pct: Percentage change in count vs the previous period
            (positive = increase, None if no previous period).
        avg_severity_weight: Mean severity numeric weight (0–4; -1 excluded).
    """

    period: str
    year: int | None
    month: str | None
    count: int
    dominant_types: list[str]
    severity_distribution: dict[str, int]
    rate_change_pct: float | None
    avg_severity_weight: float


@dataclass
class PatternAnalysis:
    """Full output of a pattern analysis run.

    Attributes:
        total_incidents: All incident records analysed (literature excluded).
        periods: Per-period stats, oldest first.
        trend_direction: Overall trend across all periods.
        acceleration: Whether the rate of change is itself changing.
        dominant_incident_types: Top-5 incident type labels across all periods.
        most_volatile_type: Incident type with the highest frequency variance
            across periods (None when fewer than 2 periods).
        severity_trend: Whether average severity is worsening or improving.
        insight: One-sentence plain-text summary of the most notable pattern.
    """

    total_incidents: int
    periods: list[PeriodStats]
    trend_direction: str  # "increasing" | "decreasing" | "stable" | "insufficient_data"
    acceleration: str  # "accelerating" | "decelerating" | "stable" | "insufficient_data"
    dominant_incident_types: list[str]
    most_volatile_type: str | None
    severity_trend: str  # "worsening" | "improving" | "stable" | "insufficient_data"
    insight: str


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


class PatternAnalyzer:
    """Detect temporal and categorical patterns in incident metadata.

    Args:
        exclude_literature: When True (default), skip records with
            ``source_type != "incident_report"`` so literature documents
            don't distort clinical trend counts.
    """

    def __init__(self, exclude_literature: bool = True) -> None:
        self.exclude_literature = exclude_literature

    def analyze(self, records: list[dict[str, Any]]) -> PatternAnalysis:
        """Analyse a list of Qdrant scroll records.

        Args:
            records: Each item is ``{"incident_id": ..., "vector": ...,
                "metadata": {...}}`` as returned by ``QdrantHandler.scroll_all()``.

        Returns:
            PatternAnalysis dataclass.
        """
        incidents = self._filter(records)
        n = len(incidents)

        if n == 0:
            return PatternAnalysis(
                total_incidents=0,
                periods=[],
                trend_direction="insufficient_data",
                acceleration="insufficient_data",
                dominant_incident_types=[],
                most_volatile_type=None,
                severity_trend="insufficient_data",
                insight="No incident records found in the store.",
            )

        buckets = self._bucket_by_period(incidents)
        sorted_periods = self._sort_periods(list(buckets.keys()))
        type_counter: Counter = Counter()

        period_stats: list[PeriodStats] = []
        for i, key in enumerate(sorted_periods):
            metas = buckets[key]
            prev_count = period_stats[i - 1].count if i > 0 else None
            stats = self._build_period_stats(key, metas, prev_count)
            period_stats.append(stats)
            for m in metas:
                for t in m.get("incident_type", []):
                    type_counter[t] += 1

        trend = self._compute_trend([p.count for p in period_stats])
        accel = self._compute_acceleration([p.count for p in period_stats])
        sev_trend = self._compute_severity_trend(period_stats)
        volatile = self._most_volatile_type(buckets, sorted_periods)
        top_types = [t for t, _ in type_counter.most_common(5)]

        insight = self._build_insight(trend, top_types, period_stats, volatile)

        logger.info(
            "PatternAnalyzer: %d incidents, %d periods, trend=%s",
            n, len(period_stats), trend,
        )

        return PatternAnalysis(
            total_incidents=n,
            periods=period_stats,
            trend_direction=trend,
            acceleration=accel,
            dominant_incident_types=top_types,
            most_volatile_type=volatile,
            severity_trend=sev_trend,
            insight=insight,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _filter(self, records: list[dict]) -> list[dict]:
        out = []
        for r in records:
            meta = r.get("metadata", {})
            if self.exclude_literature and meta.get("source_type", "incident_report") != "incident_report":
                continue
            out.append(meta)
        return out

    def _bucket_by_period(
        self, metas: list[dict]
    ) -> dict[tuple[int | None, str | None], list[dict]]:
        buckets: dict = defaultdict(list)
        for m in metas:
            key = (m.get("year"), m.get("month"))
            buckets[key].append(m)
        return dict(buckets)

    def _sort_periods(
        self, keys: list[tuple[int | None, str | None]]
    ) -> list[tuple]:
        def _key(k: tuple) -> tuple:
            yr, mo = k
            return (yr or 0, _MONTH_ORDER.get(str(mo), 99))
        return sorted(keys, key=_key)

    def _build_period_stats(
        self,
        key: tuple,
        metas: list[dict],
        prev_count: int | None,
    ) -> PeriodStats:
        year, month = key
        period_label = f"{year}-{month}" if year and month else str(year or month or "Unknown")

        type_counter: Counter = Counter(
            t for m in metas for t in m.get("incident_type", [])
        )
        sev_counter: Counter = Counter(m.get("severity", "Unknown") for m in metas)
        dominant = [t for t, _ in type_counter.most_common(3)]

        weights = [
            _SEVERITY_WEIGHT[m.get("severity", "Unknown")]
            for m in metas
            if _SEVERITY_WEIGHT.get(m.get("severity", "Unknown"), -1) >= 0
        ]
        avg_weight = round(sum(weights) / len(weights), 3) if weights else 0.0

        rate_change: float | None = None
        if prev_count is not None and prev_count > 0:
            rate_change = round(100.0 * (len(metas) - prev_count) / prev_count, 1)
        elif prev_count == 0:
            rate_change = None  # can't compute pct from zero

        return PeriodStats(
            period=period_label,
            year=year,
            month=month,
            count=len(metas),
            dominant_types=dominant,
            severity_distribution=dict(sev_counter),
            rate_change_pct=rate_change,
            avg_severity_weight=avg_weight,
        )

    @staticmethod
    def _compute_trend(counts: list[int]) -> str:
        if len(counts) < 2:
            return "insufficient_data"
        increases = sum(1 for a, b in zip(counts, counts[1:]) if b > a)
        decreases = sum(1 for a, b in zip(counts, counts[1:]) if b < a)
        pairs = len(counts) - 1
        if increases / pairs >= 0.6:
            return "increasing"
        if decreases / pairs >= 0.6:
            return "decreasing"
        return "stable"

    @staticmethod
    def _compute_acceleration(counts: list[int]) -> str:
        if len(counts) < 3:
            return "insufficient_data"
        deltas = [counts[i + 1] - counts[i] for i in range(len(counts) - 1)]
        second_deltas = [deltas[i + 1] - deltas[i] for i in range(len(deltas) - 1)]
        pos = sum(1 for d in second_deltas if d > 0)
        neg = sum(1 for d in second_deltas if d < 0)
        n = len(second_deltas)
        if pos / n >= 0.6:
            return "accelerating"
        if neg / n >= 0.6:
            return "decelerating"
        return "stable"

    @staticmethod
    def _compute_severity_trend(periods: list[PeriodStats]) -> str:
        weights = [p.avg_severity_weight for p in periods if p.avg_severity_weight > 0]
        if len(weights) < 2:
            return "insufficient_data"
        increases = sum(1 for a, b in zip(weights, weights[1:]) if b > a)
        decreases = sum(1 for a, b in zip(weights, weights[1:]) if b < a)
        pairs = len(weights) - 1
        if increases / pairs >= 0.6:
            return "worsening"
        if decreases / pairs >= 0.6:
            return "improving"
        return "stable"

    def _most_volatile_type(
        self,
        buckets: dict,
        sorted_keys: list[tuple],
    ) -> str | None:
        if len(sorted_keys) < 2:
            return None

        type_counts_per_period: dict[str, list[int]] = defaultdict(list)
        for key in sorted_keys:
            metas = buckets[key]
            counter: Counter = Counter(t for m in metas for t in m.get("incident_type", []))
            all_types = set(t for m in buckets[key] for t in m.get("incident_type", []))
            for t in all_types:
                type_counts_per_period[t].append(counter[t])

        best_type = None
        best_variance = -1.0
        for t, counts_list in type_counts_per_period.items():
            if len(counts_list) < 2:
                continue
            mean = sum(counts_list) / len(counts_list)
            variance = sum((c - mean) ** 2 for c in counts_list) / len(counts_list)
            if variance > best_variance:
                best_variance = variance
                best_type = t

        return best_type

    @staticmethod
    def _build_insight(
        trend: str,
        top_types: list[str],
        periods: list[PeriodStats],
        volatile: str | None,
    ) -> str:
        n_periods = len(periods)
        total = sum(p.count for p in periods)
        top_label = top_types[0] if top_types else "clinical incidents"

        if trend == "insufficient_data" or n_periods < 2:
            return f"{total} incident(s) analysed across {n_periods} period(s); insufficient data for trend detection."

        trend_map = {
            "increasing": "Incident volume is trending upward",
            "decreasing": "Incident volume is trending downward",
            "stable": "Incident volume is stable",
        }
        base = trend_map.get(trend, "Incident volume trend is mixed")

        if volatile:
            base += f"; most volatile incident type is '{volatile}'"

        if top_label != volatile and top_label:
            base += f"; '{top_label}' is the most frequent incident type overall"

        base += f" across {n_periods} reporting period(s)."
        return base
