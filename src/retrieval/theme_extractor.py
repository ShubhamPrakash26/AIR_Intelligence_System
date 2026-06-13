"""LLM-assisted theme naming for HDBSCAN incident clusters.

Uses Anthropic Claude via LangChain if an API key is available. Falls back
to keyword-based naming (no network calls) so tests and offline environments
work without any credentials.

Consistent with the LangChain pattern used in
src/incident/understanding_agent.py.
"""

from __future__ import annotations

import json
from typing import Any

from src.retrieval.clustering import (
    extract_root_cause_keywords,
    fallback_insight,
    fallback_recommendations,
    fallback_theme_name,
    most_common_values,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are a clinical patient safety analyst. "
    "You will receive a group of anaesthesia incidents that share similar "
    "characteristics. Identify their unifying clinical theme."
)

_USER_TEMPLATE = """These {n} incidents form a cluster. Respond with JSON only:
{{
  "theme_name": "<3-7 word clinical theme>",
  "key_insight": "<one sentence unifying safety issue>",
  "recommendations": ["<rec 1>", "<rec 2>", "<rec 3>"]
}}

Incident patterns:
{patterns}
"""


class ThemeExtractor:
    """Generate theme names and insights for a cluster of incidents.

    Uses Anthropic Claude (via LangChain ChatAnthropic) if ``ANTHROPIC_API_KEY``
    is set. Otherwise produces keyword-based fallback output.

    Inject a fake LLM object via the ``llm`` parameter in tests to control
    output without any API calls.  A fake LLM must implement
    ``invoke(messages) -> object`` where ``object.content`` is a JSON string.
    """

    def __init__(self, llm: Any = None) -> None:
        self._llm = llm
        self._tried_load = False

    def name_theme(
        self, metadata_list: list[dict[str, Any]]
    ) -> tuple[str, str, list[str]]:
        """Return ``(theme_name, key_insight, recommendations)`` for a cluster.

        Tries LLM first; falls back silently to keyword extraction on any
        failure so the clustering pipeline never raises.
        """
        if not self._tried_load and self._llm is None:
            self._llm = self._load_llm()
            self._tried_load = True

        if self._llm is not None:
            try:
                return self._llm_name(metadata_list)
            except Exception as exc:
                logger.warning("LLM theme naming failed (%s); using fallback", exc)

        return self._fallback_name(metadata_list)

    # ------------------------------------------------------------------

    def _load_llm(self) -> Any:
        """Lazy-load LangChain ChatAnthropic. Returns None if unavailable."""
        try:
            from langchain_anthropic import ChatAnthropic
            from src.utils.config import settings

            if not settings.anthropic_api_key:
                return None
            return ChatAnthropic(
                model=settings.llm_model,
                api_key=settings.anthropic_api_key,
                max_tokens=512,
                temperature=0.2,
            )
        except Exception:
            return None

    def _llm_name(
        self, metadata_list: list[dict[str, Any]]
    ) -> tuple[str, str, list[str]]:
        """Call the LLM and parse its JSON response."""
        from langchain_core.messages import HumanMessage, SystemMessage

        patterns = _summarise_for_llm(metadata_list)
        user_msg = _USER_TEMPLATE.format(n=len(metadata_list), patterns=patterns)
        response = self._llm.invoke(
            [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=user_msg)]
        )
        content = response.content if hasattr(response, "content") else str(response)
        data = json.loads(content)
        return (
            str(data.get("theme_name", "Clinical Theme")),
            str(data.get("key_insight", "")),
            list(data.get("recommendations", [])),
        )

    def _fallback_name(
        self, metadata_list: list[dict[str, Any]]
    ) -> tuple[str, str, list[str]]:
        """Keyword-based theme name when LLM is not available."""
        common_types = most_common_values(
            [t for m in metadata_list for t in m.get("incident_type", [])], n=2
        )
        common_severity = most_common_values(
            [m.get("severity", "") for m in metadata_list], n=1
        )
        root_cause_keywords = extract_root_cause_keywords(metadata_list, n=3)
        return (
            fallback_theme_name(common_types, common_severity),
            fallback_insight(root_cause_keywords, common_types),
            fallback_recommendations(common_types),
        )


def _summarise_for_llm(metadata_list: list[dict[str, Any]]) -> str:
    """Format cluster metadata as a compact text block for the LLM prompt."""
    lines: list[str] = []
    for i, m in enumerate(metadata_list[:10], 1):
        types_str = ", ".join(m.get("incident_type", ["Unknown"]))
        rc = (m.get("root_cause", "") or "")[:80]
        lines.append(
            f"{i}. {types_str} | {m.get('severity', '?')} | "
            f"{m.get('surgery_type', '?')} | {rc}"
        )
    return "\n".join(lines)
