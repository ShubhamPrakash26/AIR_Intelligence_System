"""Embedding generation engine for clinical incidents.

Wraps sentence-transformers (BGE-M3 by default) with lazy model loading,
batch processing, and a rich text builder that combines incident narratives
with AI analysis fields to maximise semantic fidelity.
"""

from __future__ import annotations

from typing import Any

from src.embeddings.models import EmbeddingResult, get_model_dimension
from src.models.analysis import AIAnalysis
from src.models.incident import Incident
from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class EmbeddingEngine:
    """Generate semantic vectors for clinical incidents using BGE-M3.

    The model is loaded lazily on first use so that importing this module
    does not trigger a 2 GB download.  Pass a pre-built ``model`` object to
    skip loading entirely — this is the recommended pattern for unit tests.

    Args:
        model_name: HuggingFace model identifier.  Defaults to the value in
            ``settings.embedding_model`` (``"BAAI/bge-m3"``).
        model: Optional pre-built SentenceTransformer instance.  When
            provided the ``model_name`` is used only for bookkeeping; no
            download is attempted.
    """

    def __init__(
        self,
        model_name: str | None = None,
        model: Any | None = None,
    ) -> None:
        self._model_name = model_name or settings.embedding_model
        self._dimension = get_model_dimension(self._model_name)
        self._model = model

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    # ------------------------------------------------------------------
    # Core embedding methods
    # ------------------------------------------------------------------

    def embed_text(self, text: str) -> list[float]:
        """Embed a single text string and return a float list."""
        model = self._load_model()
        vector = model.encode(text, normalize_embeddings=True)
        return _to_float_list(vector)

    def embed_batch(
        self,
        texts: list[str],
        batch_size: int | None = None,
    ) -> list[list[float]]:
        """Embed a list of texts in a single batched call.

        Returns a list of float vectors in the same order as ``texts``.
        Returns an empty list when ``texts`` is empty.
        """
        if not texts:
            return []

        batch_size = batch_size or settings.embedding_batch_size
        model = self._load_model()
        vectors = model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [_to_float_list(v) for v in vectors]

    # ------------------------------------------------------------------
    # Incident-level helpers
    # ------------------------------------------------------------------

    def build_embed_text(
        self,
        incident: Incident,
        analysis: AIAnalysis | None = None,
    ) -> str:
        """Build a rich plain-text representation of an incident for embedding.

        Combines the raw incident narrative with AI analysis outputs so the
        resulting vector captures both the clinical event and the system-level
        interpretation (root cause, severity, key learning).
        """
        parts: list[str] = []

        # Surgical context
        surgery = incident.surgery
        ctx = " - ".join(
            p for p in [surgery.surgical_branch, surgery.procedure, surgery.type_of_procedure] if p
        )
        if ctx:
            parts.append(f"Surgical context: {ctx}")

        # Incident narrative
        inc = incident.incident
        if inc.incident_description:
            parts.append(f"Incident: {inc.incident_description}")
        if inc.incident_details and inc.incident_details != inc.incident_description:
            parts.append(f"Details: {inc.incident_details}")
        if inc.timing_of_event:
            parts.append(f"Timing: {inc.timing_of_event}")
        if inc.place_of_incident:
            parts.append(f"Location: {inc.place_of_incident}")

        # Patient outcome
        if incident.outcome.patient_safety:
            parts.append(f"Outcome: {incident.outcome.patient_safety}")

        # Medication error context (when present)
        if incident.medication_error:
            me = incident.medication_error
            if me.type_of_error:
                parts.append(f"Medication error type: {me.type_of_error}")
            if me.cause_of_error:
                parts.append(f"Medication error cause: {me.cause_of_error}")

        # AI analysis enrichment — the most semantically valuable section
        if analysis:
            parts.append(f"Incident types: {', '.join(analysis.incident_type)}")
            parts.append(f"Severity: {analysis.severity}")
            parts.append(f"Root cause: {analysis.root_cause}")
            if analysis.contributing_factors:
                parts.append(f"Contributing factors: {'; '.join(analysis.contributing_factors)}")
            parts.append(f"Key learning: {analysis.key_learning}")
            if analysis.preventive_recommendations:
                parts.append(
                    f"Recommendations: {'; '.join(analysis.preventive_recommendations)}"
                )

        return "\n".join(parts)

    def embed_incident(
        self,
        incident: Incident,
        analysis: AIAnalysis | None = None,
    ) -> EmbeddingResult:
        """Embed a single incident and return a structured result.

        Args:
            incident: The parsed incident record.
            analysis: Optional AI analysis; when provided the vector is
                enriched with root cause, severity and key learning fields.

        Returns:
            EmbeddingResult containing the incident ID, embedded text, and
            dense float vector.
        """
        text = self.build_embed_text(incident, analysis)
        vector = self.embed_text(text)

        return EmbeddingResult(
            incident_id=incident.incident_id,
            text=text,
            vector=vector,
            model_name=self._model_name,
            dimension=len(vector),
        )

    def embed_incidents_batch(
        self,
        incidents: list[Incident],
        analyses: list[AIAnalysis] | None = None,
        batch_size: int | None = None,
    ) -> list[EmbeddingResult]:
        """Embed a batch of incidents efficiently with a single model call.

        Args:
            incidents: List of parsed incidents.
            analyses: Optional list of AI analyses; matched by ``incident_id``.
            batch_size: Override the default batch size from settings.

        Returns:
            List of EmbeddingResult objects in the same order as ``incidents``.
        """
        if not incidents:
            return []

        analysis_map: dict[str, AIAnalysis] = (
            {a.incident_id: a for a in analyses} if analyses else {}
        )

        texts = [
            self.build_embed_text(inc, analysis_map.get(inc.incident_id))
            for inc in incidents
        ]
        vectors = self.embed_batch(texts, batch_size=batch_size)

        return [
            EmbeddingResult(
                incident_id=inc.incident_id,
                text=text,
                vector=vector,
                model_name=self._model_name,
                dimension=len(vector),
            )
            for inc, text, vector in zip(incidents, texts, vectors)
        ]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_model(self) -> Any:
        """Lazy-load sentence-transformers model on first call."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise ImportError(
                    "sentence-transformers is required. "
                    "Install with: poetry add sentence-transformers"
                ) from exc

            logger.info("Loading embedding model '%s' …", self._model_name)
            self._model = SentenceTransformer(self._model_name)
            # Update dimension from the model's actual output size
            test_vec = self._model.encode("test", normalize_embeddings=True)
            self._dimension = len(test_vec)
            logger.info(
                "Embedding model loaded (dimension=%d)", self._dimension
            )

        return self._model


def _to_float_list(array: Any) -> list[float]:
    """Convert a numpy array (or anything with .tolist()) to list[float]."""
    try:
        return array.tolist()
    except AttributeError:
        return list(array)
