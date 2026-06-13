"""Unit tests for ThemeExtractor (Week 7).

All tests run offline — no Anthropic API calls are made.  A fake LLM object
with a configurable ``invoke()`` method is injected where needed.
"""

from __future__ import annotations

import json

import pytest

from src.retrieval.theme_extractor import ThemeExtractor, _summarise_for_llm


# ---------------------------------------------------------------------------
# Fake LLM
# ---------------------------------------------------------------------------


class _FakeLLM:
    """Minimal LangChain-compatible LLM stub."""

    def __init__(self, payload: dict | None = None, fail: bool = False) -> None:
        self._payload = payload or {
            "theme_name": "Equipment Safety Theme",
            "key_insight": "Recurring equipment failure pattern.",
            "recommendations": ["Audit equipment", "Train staff"],
        }
        self.fail = fail
        self.calls: int = 0

    def invoke(self, messages):
        self.calls += 1
        if self.fail:
            raise RuntimeError("LLM unavailable")

        class _Resp:
            pass

        resp = _Resp()
        resp.content = json.dumps(self._payload)
        return resp


def _meta(
    incident_type: str = "Airway",
    severity: str = "High",
    surgery_type: str = "Cardiac",
    root_cause: str = "Equipment labeling failure",
) -> dict:
    return {
        "incident_type": [incident_type],
        "severity": severity,
        "surgery_type": surgery_type,
        "root_cause": root_cause,
        "severity_score": 0.8,
    }


# ---------------------------------------------------------------------------
# ThemeExtractor — fallback (no LLM)
# ---------------------------------------------------------------------------


class TestThemeExtractorFallback:
    def test_returns_tuple_of_three(self):
        extractor = ThemeExtractor(llm=None)
        extractor._tried_load = True
        result = extractor.name_theme([_meta()])
        assert len(result) == 3

    def test_name_is_nonempty_string(self):
        extractor = ThemeExtractor(llm=None)
        extractor._tried_load = True
        name, _, _ = extractor.name_theme([_meta()])
        assert isinstance(name, str) and len(name) > 0

    def test_insight_is_string(self):
        extractor = ThemeExtractor(llm=None)
        extractor._tried_load = True
        _, insight, _ = extractor.name_theme([_meta()])
        assert isinstance(insight, str)

    def test_recommendations_is_list(self):
        extractor = ThemeExtractor(llm=None)
        extractor._tried_load = True
        _, _, recs = extractor.name_theme([_meta()])
        assert isinstance(recs, list)

    def test_incident_type_in_name(self):
        extractor = ThemeExtractor(llm=None)
        extractor._tried_load = True
        name, _, _ = extractor.name_theme([_meta(incident_type="Medication Error")] * 3)
        assert "Medication Error" in name

    def test_recommendations_nonempty(self):
        extractor = ThemeExtractor(llm=None)
        extractor._tried_load = True
        _, _, recs = extractor.name_theme([_meta()] * 3)
        assert len(recs) >= 1

    def test_severity_in_name(self):
        extractor = ThemeExtractor(llm=None)
        extractor._tried_load = True
        name, _, _ = extractor.name_theme([_meta(severity="Critical")] * 3)
        assert "Critical" in name


# ---------------------------------------------------------------------------
# ThemeExtractor — LLM path
# ---------------------------------------------------------------------------


class TestThemeExtractorLLM:
    def test_llm_result_used(self):
        extractor = ThemeExtractor(llm=_FakeLLM())
        name, insight, recs = extractor.name_theme([_meta()] * 3)
        assert name == "Equipment Safety Theme"
        assert insight == "Recurring equipment failure pattern."
        assert recs == ["Audit equipment", "Train staff"]

    def test_llm_called_once(self):
        fake = _FakeLLM()
        extractor = ThemeExtractor(llm=fake)
        extractor.name_theme([_meta()])
        assert fake.calls == 1

    def test_fallback_on_llm_failure(self):
        extractor = ThemeExtractor(llm=_FakeLLM(fail=True))
        name, insight, recs = extractor.name_theme(
            [_meta(incident_type="Equipment Failure")] * 2
        )
        assert isinstance(name, str) and len(name) > 0
        assert isinstance(recs, list)

    def test_fallback_on_invalid_json(self):
        class _BadLLM:
            def invoke(self, messages):
                class _Resp:
                    content = "not json at all"
                return _Resp()

        extractor = ThemeExtractor(llm=_BadLLM())
        name, insight, recs = extractor.name_theme([_meta(incident_type="Airway")])
        assert isinstance(name, str)

    def test_partial_json_uses_defaults(self):
        extractor = ThemeExtractor(llm=_FakeLLM(payload={"theme_name": "Partial Theme"}))
        name, insight, recs = extractor.name_theme([_meta()])
        assert name == "Partial Theme"
        assert insight == ""
        assert recs == []

    def test_no_load_attempted_when_llm_provided(self):
        fake = _FakeLLM()
        extractor = ThemeExtractor(llm=fake)
        extractor.name_theme([_meta()])
        assert extractor._tried_load is False


# ---------------------------------------------------------------------------
# _summarise_for_llm
# ---------------------------------------------------------------------------


class TestSummariseForLlm:
    def test_truncates_to_10_incidents(self):
        meta_list = [_meta()] * 15
        result = _summarise_for_llm(meta_list)
        lines = [ln for ln in result.strip().split("\n") if ln.strip()]
        assert len(lines) == 10

    def test_includes_incident_type(self):
        result = _summarise_for_llm([_meta(incident_type="Airway")])
        assert "Airway" in result

    def test_includes_severity(self):
        result = _summarise_for_llm([_meta(severity="Critical")])
        assert "Critical" in result

    def test_includes_surgery_type(self):
        result = _summarise_for_llm([_meta(surgery_type="Cardiac")])
        assert "Cardiac" in result

    def test_empty_list(self):
        result = _summarise_for_llm([])
        assert result == ""

    def test_root_cause_truncated_at_80_chars(self):
        long_rc = "x" * 200
        result = _summarise_for_llm([_meta(root_cause=long_rc)])
        assert "x" * 81 not in result
