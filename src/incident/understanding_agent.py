"""Incident understanding orchestration for Week 3 scaffolding.

This module coordinates classification and severity analysis and produces the
project's AIAnalysis model.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from src.incident.classifiers import IncidentTypeClassifier, unique_labels
from src.incident.root_cause_analyzer import RootCauseAnalyzer
from src.incident.severity_analyzer import SeverityAnalyzer
from src.models.analysis import AIAnalysis, IncidentUnderstandingResponse
from src.models.incident import Incident
from src.utils.config import settings


DEFAULT_SYSTEM_PROMPT = (
    "You are a clinical incident understanding agent. Summarize the incident, "
    "classify likely incident types, estimate severity, identify root cause, "
    "and suggest preventive learning."
)

DEFAULT_USER_PROMPT = (
    "Return JSON with keys incident_type, severity, severity_score, root_cause, "
    "contributing_factors, contributing_factor_categories, key_learning, "
    "preventive_recommendations, confidence_score, processing_notes."
)


@dataclass(frozen=True)
class UnderstandingResult:
    """Combined analysis output."""

    analysis: AIAnalysis
    system_prompt: str = DEFAULT_SYSTEM_PROMPT


class UnderstandingGraphState(TypedDict):
    """Mutable state for the LangGraph workflow."""

    incident: Incident
    system_prompt: str
    user_prompt: str
    classification_result: dict[str, Any]
    severity_result: dict[str, Any]
    llm_payload: dict[str, Any] | None
    analysis: AIAnalysis | None
    error: str | None


class IncidentUnderstandingAgent:
    """Coordinate heuristic analysis components for a parsed incident."""

    def __init__(self, llm: Any | None = None) -> None:
        self.classifier = IncidentTypeClassifier()
        self.severity_analyzer = SeverityAnalyzer()
        self.root_cause_analyzer = RootCauseAnalyzer()
        self.system_prompt = DEFAULT_SYSTEM_PROMPT
        self.user_prompt = DEFAULT_USER_PROMPT
        self.llm = llm or self._build_default_llm()
        self.structured_llm = self._build_structured_llm(self.llm)
        self.graph = self._build_graph()

    def analyze_incident(self, incident: Incident) -> UnderstandingResult:
        state = self.graph.invoke(
            {
                "incident": incident,
                "system_prompt": self.system_prompt,
                "user_prompt": self.user_prompt,
                "classification": {},
                "severity": {},
                "llm_payload": None,
                "analysis": None,
                "error": None,
            }
        )
        analysis = state["analysis"]
        if analysis is None:
            raise RuntimeError(state.get("error") or "Incident analysis failed")
        return UnderstandingResult(analysis=analysis)

    def _build_default_llm(self) -> Any | None:
        if not settings.anthropic_api_key:
            return None

        try:
            from langchain_anthropic import ChatAnthropic
        except Exception:
            return None

        return ChatAnthropic(
            model=settings.llm_model,
            max_tokens=settings.max_tokens,
            api_key=settings.anthropic_api_key,
        )

    def _build_structured_llm(self, llm: Any | None) -> Any | None:
        if llm is None:
            return None
        structured_output = getattr(llm, "with_structured_output", None)
        if callable(structured_output):
            return structured_output(IncidentUnderstandingResponse)
        return None

    def _build_graph(self):
        graph = StateGraph(UnderstandingGraphState)
        graph.add_node("classify", self._classify_node)
        graph.add_node("severity_analysis", self._severity_node)
        graph.add_node("analyze", self._analysis_node)
        graph.add_node("llm", self._llm_node)
        graph.add_edge("classify", "severity_analysis")
        graph.add_edge("severity_analysis", "analyze")
        graph.add_conditional_edges("analyze", self._route_after_analysis, {"llm": "llm", "end": END})
        graph.add_edge("llm", END)
        graph.set_entry_point("classify")
        return graph.compile()

    def _classify_node(self, state: UnderstandingGraphState) -> UnderstandingGraphState:
        result = self.classifier.classify_incident(state["incident"])
        state["classification_result"] = {
            "labels": result.labels,
            "confidence": result.confidence,
            "matched_keywords": result.matched_keywords,
        }
        return state

    def _severity_node(self, state: UnderstandingGraphState) -> UnderstandingGraphState:
        result = self.severity_analyzer.analyze_incident(state["incident"])
        state["severity_result"] = {"severity": result.severity, "score": result.score, "rationale": result.rationale}
        return state

    def _analysis_node(self, state: UnderstandingGraphState) -> UnderstandingGraphState:
        classification = state["classification_result"]
        severity = state["severity_result"]
        root_cause = self.root_cause_analyzer.analyze_incident(
            state["incident"],
            incident_types=classification["labels"],
            severity=severity["severity"],
        )

        analysis = AIAnalysis(
            incident_id=state["incident"].incident_id,
            incident_type=unique_labels(classification["labels"]),
            severity=severity["severity"],
            severity_score=severity["score"],
            root_cause=root_cause.root_cause,
            contributing_factors=root_cause.contributing_factors,
            contributing_factor_categories=root_cause.contributing_factor_categories,
            key_learning=root_cause.key_learning,
            preventive_recommendations=root_cause.preventive_recommendations,
            confidence_score=classification["confidence"],
            validation_status="pending",
            validation_errors=None,
            processing_timestamp=datetime.now(timezone.utc).isoformat(),
            model_version="week3-graph-scaffold-0.2",
            processing_notes=severity["rationale"],
        )
        state["analysis"] = analysis
        return state

    def _route_after_analysis(self, state: UnderstandingGraphState) -> str:
        if self.llm is None:
            return "end"
        return "llm"

    def _llm_node(self, state: UnderstandingGraphState) -> UnderstandingGraphState:
        if self.llm is None:
            return state

        incident = state["incident"]
        messages = [
            SystemMessage(content=state["system_prompt"]),
            HumanMessage(content=self._build_user_message(incident, state)),
        ]
        response = self.structured_llm.invoke(messages) if self.structured_llm is not None else self.llm.invoke(messages)
        state["llm_payload"] = self._parse_llm_response(response)
        state["analysis"] = self._merge_llm_payload(state)
        return state

    def _build_user_message(self, incident: Incident, state: UnderstandingGraphState) -> str:
        return "\n".join(
            [
                state["user_prompt"],
                f"incident_id: {incident.incident_id}",
                f"incident_description: {incident.incident.incident_description or ''}",
                f"incident_details: {incident.incident.incident_details or ''}",
                f"patient_safety: {incident.outcome.patient_safety or ''}",
                f"classification_hint: {state['classification_result']['labels']}",
                f"severity_hint: {state['severity_result']['severity']}",
            ]
        )

    def _parse_llm_response(self, response: Any) -> IncidentUnderstandingResponse:
        if isinstance(response, IncidentUnderstandingResponse):
            return response

        content = getattr(response, "content", response)
        if isinstance(content, IncidentUnderstandingResponse):
            return content

        if isinstance(content, dict):
            return IncidentUnderstandingResponse.model_validate(content)

        if isinstance(content, str):
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError as exc:
                raise ValueError("LLM response was not valid JSON") from exc
            if not isinstance(parsed, dict):
                raise ValueError("LLM response JSON must be an object")
            return IncidentUnderstandingResponse.model_validate(parsed)

        raise ValueError("LLM response format not supported")

    def _merge_llm_payload(self, state: UnderstandingGraphState) -> AIAnalysis:
        payload = state["llm_payload"] or {}
        analysis = state["analysis"]
        assert analysis is not None

        payload_dump = payload.model_dump(mode="json")

        if "incident_type" in payload_dump:
            analysis.incident_type = unique_labels(list(payload_dump["incident_type"]))
        if "severity" in payload_dump:
            analysis.severity = str(payload_dump["severity"])
        if "severity_score" in payload_dump:
            analysis.severity_score = float(payload_dump["severity_score"])
        # Preserve the deterministic RCA-derived `root_cause` for consistency.
        # Do not override it with the LLM's (often verbose) `root_cause` field,
        # which can vary by model and reduce test determinism.
        # If you want LLM-suggested root causes in future, add a separate
        # field such as `llm_root_cause` and keep RCA as the canonical value.
        if "contributing_factors" in payload_dump:
            analysis.contributing_factors = list(payload_dump["contributing_factors"])
        if "contributing_factor_categories" in payload_dump and payload_dump["contributing_factor_categories"] is not None:
            analysis.contributing_factor_categories = list(payload_dump["contributing_factor_categories"])
        if "key_learning" in payload_dump:
            analysis.key_learning = str(payload_dump["key_learning"])
        if "preventive_recommendations" in payload_dump and payload_dump["preventive_recommendations"] is not None:
            analysis.preventive_recommendations = list(payload_dump["preventive_recommendations"])
        if "confidence_score" in payload_dump:
            analysis.confidence_score = float(payload_dump["confidence_score"])
        if "processing_notes" in payload_dump:
            analysis.processing_notes = str(payload_dump["processing_notes"])
        return analysis

