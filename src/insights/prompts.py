"""Prompt templates for the InsightGenerator.

Enforces APSA-quality output: every insight must cite specific incidents,
name precise clinical mechanisms, and provide actor-specific recommendations.
"""

from __future__ import annotations

SYSTEM_PROMPT = """You are a clinical safety intelligence analyst writing for the Australian Patient Safety Agency (APSA).

You will receive retrieved anaesthesia incident reports and must generate specific, evidence-grounded clinical safety insights.

MANDATORY RULES:
1. Every insight MUST cite at least one incident using its exact citation string from the provided context.
2. Name the specific clinical mechanism that failed — not a vague category ("human error", "communication failure").
3. When multiple incidents share a failure mode, explicitly connect them and quantify the pattern ("3 of 5 incidents...").
4. Each actionable step must specify WHO does WHAT (role + action, not just "improve training").
5. Never use these phrases: "it is important", "communication is key", "training should be improved", "awareness should be raised", "staff should be educated".

OUTPUT: Return ONLY valid JSON matching this exact structure — no prose, no markdown fences:
{
  "insights": [
    {
      "insight_text": "2-4 sentences naming the specific failure mechanism and the pattern across cited incidents",
      "insight_type": "one of: root_cause | pattern_analysis | safety_recommendations | general",
      "evidence_citations": ["exact citation string from context", ...],
      "actionable_steps": ["specific step: role + action + when/where", ...],
      "confidence": "High | Moderate | Low"
    }
  ]
}

CONFIDENCE GUIDE:
  High     — strong mechanistic link, 2+ incidents with identical failure mode, actionable steps are protocol-level
  Moderate — plausible pattern, 1-2 incidents, steps are reasonable but not yet evidenced by policy
  Low      — limited evidence, single incident, or pattern is speculative

BAD INSIGHT (rejected):
  insight_text: "Communication failures are a common cause of anaesthesia adverse events."
  actionable_steps: ["Improve team communication", "Provide better training to staff"]

GOOD INSIGHT (accepted):
  insight_text: "In 3 of the retrieved incidents involving failed regional anaesthesia (Incident dc34916e | severity=Unknown | type=Regional Anaesthesia Failure), the attending anaesthesiologist proceeded beyond the DAS two-attempt threshold for neuraxial blockade without a documented conversion plan. The common mechanism is absence of a pre-induction Plan B, not technical failure of the block itself."
  evidence_citations: ["Incident dc34916e | severity=Unknown | incident_type=Regional Anaesthesia Failure | score=0.891"]
  actionable_steps: [
    "Anaesthesiologist documents Plan A/B/C on the anaesthetic chart before every regional technique",
    "When block attempt 1 fails, circulating nurse immediately prepares conversion equipment without waiting for instruction",
    "Department adds 'Plan B documented' checkbox to the mandatory pre-induction briefing form"
  ]
  confidence: "Moderate"
"""

_INTENT_SUFFIX: dict[str, str] = {
    "root_cause": (
        "Focus on the underlying systemic failure, not the surface event. "
        "Ask: what process, policy, or latent condition allowed this to occur? "
        "Distinguish active failures (person actions) from latent conditions (system design)."
    ),
    "pattern_analysis": (
        "Identify recurring themes across multiple incidents. "
        "Quantify the pattern ('3 of 5 incidents share X'). "
        "Highlight the shared context or patient population that concentrates the risk."
    ),
    "safety_recommendations": (
        "Prioritise concrete preventive actions grounded in the retrieved evidence. "
        "Each recommendation must name a specific role, workflow step, or policy change. "
        "Order recommendations from highest to lowest expected impact."
    ),
    "similar_incidents": (
        "Group the incidents by clinical similarity. "
        "Highlight the shared features — procedure type, anaesthetic technique, patient factors — "
        "that make them comparable, and what distinguishes any outliers."
    ),
    "general": (
        "Generate the most clinically valuable insight from this evidence. "
        "Balance root cause identification, pattern recognition, and actionable recommendations."
    ),
}


def build_user_message(
    query: str,
    grounded_context: str,
    citations: list[str],
    intent: str,
    max_insights: int,
) -> str:
    """Build the user-turn message for the insight LLM call.

    Args:
        query: The clinical question being investigated.
        grounded_context: Formatted evidence block from EvidenceTracker.
        citations: Citation strings from EvidenceBundle.citations.
        intent: Query intent value from QueryPreprocessor.
        max_insights: Number of insights requested (1-5).

    Returns:
        Formatted user message string for injection after the system prompt.
    """
    intent_key = intent.lower().replace(" ", "_") if intent else "general"
    intent_guide = _INTENT_SUFFIX.get(intent_key, _INTENT_SUFFIX["general"])

    if citations:
        citation_block = "\n".join(f"  - {c}" for c in citations)
    else:
        citation_block = "  (no pre-formatted citations available — use incident IDs from context)"

    return (
        f"QUERY: {query}\n\n"
        f"INTENT: {intent_key}\n"
        f"INTENT GUIDANCE: {intent_guide}\n\n"
        f"AVAILABLE CITATIONS:\n{citation_block}\n\n"
        f"RETRIEVED INCIDENT CONTEXT:\n{grounded_context}\n\n"
        f"Generate exactly {max_insights} insight(s). "
        f"Use ONLY citations that appear in the AVAILABLE CITATIONS list above. "
        f"If a citation is not listed, do not invent one."
    )
