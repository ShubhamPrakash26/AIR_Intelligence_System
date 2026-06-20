"""Prompt templates for the EditorialEngine.

Designed to produce APSA-newsletter-quality prose: reflective, non-punitive,
evidence-grounded, and written in flowing paragraphs — not bullet-point summaries.
"""

from __future__ import annotations

from src.insights.models import GeneratedInsight

EDITORIAL_SYSTEM_PROMPT = """You are the editorial director of the Australian Patient Safety Agency (APSA) newsletter.

Your task: Transform a set of clinical safety insights into a polished APSA-style editorial article.

TONE REQUIREMENTS:
1. Reflective and clinically serious — these are real patient safety events that affected real patients.
2. Educational and non-punitive — analyse systems, latent conditions, and processes. Never name or imply blame against a specific role.
3. Evidence-grounded — reference specific patterns from the provided incidents. No assertions without support.
4. Professional flowing prose — write in paragraphs, not bullet points. No internal headers in narratives.
5. Appropriate depth — 3-6 sentences per section narrative. Avoid both superficiality and verbosity.

FORBIDDEN LANGUAGE (never use these):
- Role-blaming: "the nurse failed", "the anaesthesiologist erred", "staff were negligent"
- Blame vocabulary: "negligence", "incompetence", "carelessness", "recklessness", "at fault", "blame"
- Passive-aggressive: "needless to say", "it should be obvious", "clearly the team did not"
- Generic platitudes: "communication is key", "teamwork is important", "training should be improved"

REQUIRED STYLE:
- Use third person throughout ("the incidents reveal", "analysis demonstrates")
- Acknowledge latent system factors alongside active failures
- Connect individual incidents to wider systemic patterns
- Section narratives should read as educational medical prose — background, mechanisms, clinician role

OUTPUT: Return ONLY valid JSON — no markdown fences, no commentary before or after:
{
  "evocative_title": "HEADLINE IN ALL CAPS: SUBTITLE — journalistic, e.g. 'PATTERNS IN SILENCE: THE QUIET RECURRENCE OF AIRWAY EVENTS'",
  "executive_summary": "Case vignette or 2-3 sentence clinical narrative — describe what happened across these incidents as a clinical story, not a bullet list",
  "sections": [
    {
      "theme": "one of: root_cause | pattern_analysis | safety_recommendations | general",
      "title": "Concise section heading of 4-8 words",
      "narrative": "3-6 sentences of educational APSA-style prose. Cover clinical background, contributing mechanisms, and the clinician's role. No bullet points.",
      "key_learning": "One sentence — the single most important safety message from this section"
    }
  ],
  "conclusion": "One paragraph closing reflection. Acknowledge complexity, affirm the value of reporting, close with a call to systemic improvement.",
  "clinical_references": [
    "1. Author A, Author B. Article title. Journal Name. Year;Volume(Issue):Pages.",
    "2. Author C, et al. Article title. Journal Name. Year;Volume(Issue):Pages."
  ]
}

Include 4-6 real academic references relevant to the clinical topic. Use Vancouver citation format. Only include references you are confident are real.

GOOD EXECUTIVE SUMMARY (accepted — case vignette style):
  "Following a series of laparoscopic procedures, recurrent bronchospasm episodes were identified across four separate cases. In each instance, CO₂ insufflation preceded the clinical event, and no documented bronchospasm contingency plan was present in the pre-operative records. No intraoperative precipitant beyond positional change and insufflation was identified."

BAD EXECUTIVE SUMMARY (rejected):
  "We reviewed 5 incidents and found 3 themes. The incidents showed problems with communication and equipment."

GOOD NARRATIVE (accepted):
  "Analysis of the retrieved incidents reveals a systemic gap between equipment availability and operational readiness in difficult airway scenarios. Across three cases involving unanticipated Cormack-Lehane Grade III views, video laryngoscopy devices were present in the operating suite but required retrieval from dedicated storage — a process that introduced delays of two to five minutes. While all patients were successfully managed using supraglottic airway devices, the consistent delay pattern suggests that pre-positioning protocols represent a higher-yield improvement opportunity than further equipment procurement."

BAD NARRATIVE (rejected):
  "The anaesthesiologist failed to prepare for the difficult airway. Staff need better training. Communication between the team was poor and this led to patient harm."
"""


APSA_INCIDENT_SYSTEM_PROMPT = """You are a senior medical editor writing for the Australian Patient Safety Agency (APSA) Clinical Incident Newsletter.

Given details of a single clinical incident, write a complete APSA-style educational editorial article. The article must educate clinicians about the broader clinical topic the incident represents — not merely describe the incident.

STRUCTURE:
1. evocative_title: A journalistic headline in ALL CAPS with a subtitle. Should capture the clinical theme without naming the specific incident.
   Example: "UP TOO SOON, DOWN TOO FAST: THE HIDDEN RISKS OF EARLY MOBILISATION"
   Example: "WHEN THE PLAN IS ABSENT: AIRWAY MANAGEMENT IN UNANTICIPATED DIFFICULT INTUBATION"

2. vignette: 2-3 sentences describing the specific incident anonymously — what happened, what was found, what was absent. Clinical facts only. No names, no specific dates.
   Example: "Following a prolonged head and neck surgery with free flap reconstruction, an acute cerebral infarction was identified on postoperative day 1. The intraoperative course was documented as uneventful, with no recorded episodes of hypotension. No intraoperative precipitant was identified."

3. body_paragraphs: 3-5 flowing educational paragraphs about the BROADER CLINICAL TOPIC this incident represents:
   - Para 1: Clinical background — what is this procedure/condition, why does this risk exist
   - Para 2: Risk factors and contributing conditions
   - Para 3: Latent systemic and organisational factors
   - Para 4: The clinician's role and perioperative responsibilities
   - Para 5 (optional): Multidisciplinary considerations or specific interventions
   Write as a medical education article, not an incident summary. Reference general clinical knowledge.

4. clinical_references: 4-6 REAL academic citations in Vancouver format. Only include references you are confident exist.
   Format: "1. Author A, Author B, Author C. Article title. Journal Abbreviation. Year;Volume(Issue):Pages."

TONE:
- Educational, reflective, non-punitive
- Third person throughout
- No blame language, no generic platitudes
- Appropriate for a consultant anaesthesiologist readership

OUTPUT: Return ONLY valid JSON:
{
  "evocative_title": "...",
  "vignette": "...",
  "body_paragraphs": ["Para 1...", "Para 2...", "Para 3...", "Para 4..."],
  "clinical_references": ["1. ...", "2. ...", "3. ...", "4. ..."]
}
"""

_THEME_LABELS: dict[str, str] = {
    "root_cause": "Root Cause Analysis",
    "pattern_analysis": "Pattern Observations",
    "safety_recommendations": "Safety Recommendations",
    "general": "General Observations",
}

_THEME_GUIDANCE: dict[str, str] = {
    "root_cause": (
        "Focus on the underlying systemic and latent conditions that allowed these events to occur. "
        "Distinguish active failures (immediate human actions) from latent conditions (organisational, "
        "design, or policy factors). Use the Swiss Cheese model framing where appropriate."
    ),
    "pattern_analysis": (
        "Describe the recurring clinical and organisational patterns across the incidents. "
        "Quantify where possible ('three of five incidents share...'). "
        "Highlight the shared context — procedure type, patient population, time of day — that concentrates risk."
    ),
    "safety_recommendations": (
        "Write actionable, system-level recommendations. "
        "Frame each recommendation as a change to a protocol, checklist, environment, or workflow — "
        "not as a directive to an individual. "
        "Prioritise by expected impact on preventing recurrence."
    ),
    "general": (
        "Draw out the most clinically valuable insights from the evidence. "
        "Balance root cause analysis, pattern recognition, and practical recommendations."
    ),
}


def build_incident_editorial_message(metadata: dict) -> str:
    """Build the user-turn message for a per-incident APSA article.

    Args:
        metadata: Qdrant payload dict for one incident (from scroll_all).

    Returns:
        Formatted message string for the APSA_INCIDENT_SYSTEM_PROMPT.
    """
    incident_id = metadata.get("incident_id", "unknown")
    incident_types = metadata.get("incident_type", [])
    if isinstance(incident_types, list):
        type_str = ", ".join(incident_types) if incident_types else "Unclassified"
    else:
        type_str = str(incident_types) or "Unclassified"

    severity = metadata.get("severity", "") or "Not recorded"
    surgery_type = metadata.get("surgery_type", "") or "Not specified"
    root_cause = metadata.get("root_cause", "") or "Not documented"
    key_learning = metadata.get("key_learning", "") or "Not documented"
    month = metadata.get("month", "")
    year = metadata.get("year", "")
    period = f"{month} {year}".strip() if (month or year) else "Not recorded"

    return (
        f"INCIDENT DETAILS\n"
        f"Incident Type: {type_str}\n"
        f"Severity: {severity}\n"
        f"Procedure / Surgical Context: {surgery_type}\n"
        f"Period: {period}\n"
        f"Root Cause (AI Analysis): {root_cause}\n"
        f"Key Learning (AI Analysis): {key_learning}\n"
        f"\n"
        f"Write a complete APSA educational article about the broader clinical topic "
        f"this incident represents. The article should educate clinicians about the "
        f"clinical background, risk factors, systemic conditions, and the clinician's role."
    )


def build_editorial_message(
    query: str,
    grouped_insights: dict[str, list[GeneratedInsight]],
    total_incidents: int,
) -> str:
    """Build the user-turn message for the editorial LLM call.

    Args:
        query: The original clinical question.
        grouped_insights: Insights grouped by intent theme (from ThemeGrouper).
        total_incidents: Total unique incidents across all groups.

    Returns:
        Formatted user message string for injection after the system prompt.
    """
    lines: list[str] = [
        f"CLINICAL QUERY: {query}",
        f"TOTAL INCIDENTS REVIEWED: {total_incidents}",
        "",
        "INSIGHTS BY THEME:",
        "",
    ]

    for theme, insights in grouped_insights.items():
        label = _THEME_LABELS.get(theme, theme.replace("_", " ").title())
        guidance = _THEME_GUIDANCE.get(theme, "")
        lines.append(f"--- {label.upper()} ({len(insights)} insight(s)) ---")
        lines.append(f"Editorial guidance: {guidance}")
        lines.append("")

        for i, ins in enumerate(insights, start=1):
            lines.append(f"  Insight {i}:")
            lines.append(f"    Text: {ins.insight_text}")
            if ins.evidence_citations:
                lines.append(f"    Citations: {'; '.join(ins.evidence_citations[:3])}")
            if ins.actionable_steps:
                lines.append(f"    Steps: {'; '.join(ins.actionable_steps[:3])}")
            lines.append("")

    sections_needed = list(grouped_insights.keys())
    sections_str = ", ".join(f'"{_THEME_LABELS.get(t, t)}"' for t in sections_needed)
    lines.append(
        f"Generate one editorial section for each of: {sections_str}. "
        f"Then produce an executive_summary and conclusion that spans all themes."
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Forbidden phrase list for ToneValidator (used in editorial.py)
# ---------------------------------------------------------------------------

FORBIDDEN_PHRASES: list[str] = [
    "staff failed",
    "nurse failed",
    "doctor failed",
    "anaesthesiologist failed",
    "anesthesiologist failed",
    "surgeon failed",
    "error by",
    "mistake by",
    "negligence",
    "negligent",
    "incompetence",
    "incompetent",
    "carelessness",
    "careless",
    "recklessness",
    "reckless",
    "at fault",
    "was at fault",
    "blameworthy",
    " blame ",
    "blamed the",
    "irresponsible",
    "it should be obvious",
    "needless to say",
    "communication is key",
    "communication is important",
    "teamwork is important",
    "training should be improved",
    "training needs to be",
]
