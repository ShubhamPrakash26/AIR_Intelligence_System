"""Week 5 + Week 6 interactive demo - runs fully offline with no model download.

Uses a deterministic fake embedding model and in-memory Qdrant so you can see
the entire pipeline (embed -> store -> search -> rerank -> RAG) in ~5 seconds.

Run:
    poetry run python scripts/demo_retrieval.py

To use the real BGE-M3 model (~2 GB download, one-time):
    poetry run python scripts/demo_retrieval.py --real-model
"""

from __future__ import annotations

import sys
import uuid
from typing import Any

import numpy as np


# ---------------------------------------------------------------------------
# Fake models (offline, deterministic)
# ---------------------------------------------------------------------------


class _FakeEmbeddingModel:
    """Produces hash-seeded deterministic vectors - no download required.

    DIM matches the BAAI/bge-m3 registry entry (1024) so the EmbeddingEngine
    dimension property stays consistent with what we actually store in Qdrant.
    """
    DIM = 1024

    def encode(
        self,
        input_: Any,
        batch_size: int = 32,
        show_progress_bar: bool = False,
        convert_to_numpy: bool = True,
        normalize_embeddings: bool = False,
    ) -> np.ndarray:
        if isinstance(input_, str):
            seed = hash(input_) & 0xFFFF_FFFF
            v = np.random.default_rng(seed).random(self.DIM).astype(np.float32)
            v /= np.linalg.norm(v) + 1e-9
            return v

        result = []
        for text in input_:
            seed = hash(text) & 0xFFFF_FFFF
            v = np.random.default_rng(seed).random(self.DIM).astype(np.float32)
            v /= np.linalg.norm(v) + 1e-9
            result.append(v)
        return np.array(result, dtype=np.float32)


class _FakeCrossEncoder:
    """Scores (query, doc) pairs by keyword overlap count."""

    def rank(
        self,
        query: str,
        documents: list[str],
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        query_words = set(query.lower().split())
        scored = []
        for i, doc in enumerate(documents):
            doc_words = set(doc.lower().split())
            score = float(len(query_words & doc_words)) + 0.01 * len(doc)
            scored.append({"corpus_id": i, "score": score})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k] if top_k else scored

    def predict(self, pairs: list[list[str]]) -> np.ndarray:
        results = []
        for q, d in pairs:
            qw = set(q.lower().split())
            dw = set(d.lower().split())
            results.append(float(len(qw & dw)))
        return np.array(results)


# ---------------------------------------------------------------------------
# Sample incidents
# ---------------------------------------------------------------------------


SAMPLE_INCIDENTS = [
    {
        "description": "Patient received wrong drug during induction. Suxamethonium administered instead of vecuronium due to look-alike ampoules.",
        "surgery": "Colorectal",
        "severity": "High",
        "incident_type": ["Medication Error"],
        "root_cause": "Look-alike medication ampoules without distinct labeling",
        "key_learning": "Store suxamethonium and vecuronium in separate clearly labeled areas. Implement double-check protocol.",
    },
    {
        "description": "Endotracheal tube displaced during patient positioning for spinal surgery. SpO2 dropped to 82% before detected.",
        "surgery": "Spinal",
        "severity": "Critical",
        "incident_type": ["Airway", "Equipment"],
        "root_cause": "Inadequate tube fixation and position check protocol during patient turning",
        "key_learning": "Mandatory tube position verification after every patient repositioning using capnography and bilateral chest auscultation.",
    },
    {
        "description": "Anaphylaxis to latex during arthroscopy. Patient had documented latex allergy not flagged in pre-op checklist.",
        "surgery": "Orthopaedic",
        "severity": "Critical",
        "incident_type": ["Allergy", "Communication"],
        "root_cause": "Pre-operative allergy screening not integrated with surgical booking system",
        "key_learning": "Electronic allergy alerts must propagate from booking to theatre management system.",
    },
    {
        "description": "Epidural needle placed at wrong level (L2-L3 instead of L3-L4) due to landmark identification failure.",
        "surgery": "Obstetric",
        "severity": "Moderate",
        "incident_type": ["Technique Error"],
        "root_cause": "Poor landmark identification in obese patient; no ultrasound guidance used",
        "key_learning": "Ultrasound-guided epidural placement should be standard for BMI > 35.",
    },
    {
        "description": "Syringe swap: patient received 10x dose of adrenaline during cardiac bypass due to unlabeled syringes.",
        "surgery": "Cardiac",
        "severity": "Critical",
        "incident_type": ["Medication Error", "Equipment"],
        "root_cause": "Unlabeled syringes in high-pressure environment; no independent drug verification",
        "key_learning": "All syringes must be labeled immediately on drawing. Two-person verification for vasoactive drugs.",
    },
    {
        "description": "Post-op respiratory arrest due to residual neuromuscular blockade. Train-of-four monitoring not performed before extubation.",
        "surgery": "General",
        "severity": "High",
        "incident_type": ["Airway", "Monitoring"],
        "root_cause": "Inconsistent neuromuscular monitoring protocol; sugammadex not administered",
        "key_learning": "Train-of-four ratio > 0.9 is mandatory before extubation. Sugammadex should be available at all times.",
    },
    {
        "description": "Equipment failure: vaporiser delivered incorrect volatile concentration. Awareness under anaesthesia suspected.",
        "surgery": "Gynaecology",
        "severity": "High",
        "incident_type": ["Equipment", "Awareness"],
        "root_cause": "Vaporiser not calibrated as per service schedule; no BIS monitor in use",
        "key_learning": "Daily vaporiser checks and BIS monitoring for TIVA cases. Strict calibration compliance.",
    },
    {
        "description": "Wrong patient operated: consent form had correct name but surgical site marked on wrong side of body.",
        "surgery": "ENT",
        "severity": "Critical",
        "incident_type": ["Wrong Site", "Communication"],
        "root_cause": "WHO surgical checklist time-out performed incorrectly; marking not verified by patient",
        "key_learning": "Time-out must include patient verbal confirmation of site and side. Surgeon must re-examine the mark.",
    },
]


# ---------------------------------------------------------------------------
# Build Incident objects
# ---------------------------------------------------------------------------


def _build_incidents():
    """Build Incident objects from sample data."""
    from src.models.incident import (
        AnesthesiaTechnique,
        ContextMetadata,
        IncidentDetails,
        OutcomeInfo,
        PatientInfo,
        SurgeryInfo,
    )
    from src.models.incident import Incident

    incidents = []
    for s in SAMPLE_INCIDENTS:
        incidents.append(
            Incident(
                incident_id=str(uuid.uuid4()),
                patient=PatientInfo(age_range="31-50 years", sex="Female", asa_grade="II"),
                surgery=SurgeryInfo(surgical_branch=s["surgery"], type_of_procedure="Elective"),
                incident=IncidentDetails(
                    incident_type=s["incident_type"],
                    incident_description=s["description"],
                    timing_of_event="On induction",
                ),
                anesthesia=AnesthesiaTechnique(primary_technique="General Anaesthesia"),
                outcome=OutcomeInfo(harm_severity=s["severity"]),
                metadata=ContextMetadata(year=2024, source_file="demo"),
            )
        )
    return incidents, SAMPLE_INCIDENTS


# ---------------------------------------------------------------------------
# Main demo
# ---------------------------------------------------------------------------


def run_demo(use_real_model: bool = False) -> None:
    print("=" * 70)
    print("  AIR Intelligence Engine - Week 5 + Week 6 Feature Demo")
    print("=" * 70)

    # ------------------------------------------------------------------
    # 1. Setup
    # ------------------------------------------------------------------
    print("\n[1/5] Setting up embedding engine and vector store...")

    from qdrant_client import QdrantClient
    from src.embeddings.engine import EmbeddingEngine
    from src.retrieval.rag import RAGRetriever
    from src.retrieval.reranker import CrossEncoderReranker
    from src.retrieval.similarity_search import SearchFilters, SimilaritySearchEngine
    from src.vector_store.metadata import extract_metadata
    from src.vector_store.qdrant_handler import QdrantHandler

    if use_real_model:
        print("  -> Loading real BGE-M3 (this may take a while on first run)...")
        engine = EmbeddingEngine(model_name="BAAI/bge-m3")
        reranker = CrossEncoderReranker(model_name="BAAI/bge-reranker-large")
    else:
        print("  -> Using fake models (offline, instant)")
        engine = EmbeddingEngine(model=_FakeEmbeddingModel())
        reranker = CrossEncoderReranker(model=_FakeCrossEncoder())

    mem_client = QdrantClient(location=":memory:")
    store = QdrantHandler(client=mem_client)
    store.ensure_collection(dimension=engine.dimension)
    print(f"  OK Collection 'incidents' created (dim={engine.dimension})")

    # ------------------------------------------------------------------
    # 2. Embed + store all sample incidents (Week 5)
    # ------------------------------------------------------------------
    print(f"\n[2/5] Embedding and storing {len(SAMPLE_INCIDENTS)} sample incidents...")

    incidents, raw = _build_incidents()
    for i, (incident, sample) in enumerate(zip(incidents, raw), start=1):
        embed_result = engine.embed_incident(incident)
        metadata = extract_metadata(incident)
        store.upsert(incident.incident_id, embed_result.vector, metadata)
        print(f"  [{i:02d}] Stored: {sample['surgery']:15s} | {sample['severity']:8s} | {', '.join(sample['incident_type'])}")

    info = store.collection_info()
    print(f"\n  OK Qdrant: {info['points_count']} incidents stored")

    # ------------------------------------------------------------------
    # 3. Similarity search (Week 6)
    # ------------------------------------------------------------------
    print("\n[3/5] Similarity search examples...")
    search_engine = SimilaritySearchEngine(engine, store)

    queries = [
        ("medication labeling mix-up wrong drug", None),
        ("airway obstruction after patient positioning", None),
        ("cardiac surgery high severity critical error", SearchFilters(severity="Critical")),
    ]

    for query, filters in queries:
        label = f" + filter(severity=Critical)" if filters else ""
        print(f"\n  Query: \"{query}\"{label}")
        results = search_engine.search_by_text(query, top_k=3, filters=filters)
        for r in results:
            print(f"    #{r.rank}  score={r.score:.3f}  {r.surgery_type:15s}  "
                  f"{r.severity:8s}  {', '.join(r.incident_type)}")
            if r.root_cause:
                print(f"          -> {r.root_cause[:75]}..." if len(r.root_cause) > 75 else f"          -> {r.root_cause}")

    # ------------------------------------------------------------------
    # 4. Search similar to stored (Week 6 - no re-embedding)
    # ------------------------------------------------------------------
    print("\n[4/5] Search-similar-to-stored (uses stored vector, no re-embed)...")

    ref = incidents[4]  # cardiac syringe swap
    similar = search_engine.search_similar_to_stored(ref.incident_id, top_k=3, exclude_self=True)
    print(f"  Reference: [{SAMPLE_INCIDENTS[4]['surgery']}] {SAMPLE_INCIDENTS[4]['description'][:60]}...")
    print("  Similar incidents:")
    for r in similar:
        print(f"    #{r.rank}  score={r.score:.3f}  {r.surgery_type:15s}  "
              f"{r.severity:8s}  {', '.join(r.incident_type)}")

    # ------------------------------------------------------------------
    # 5. Full RAG with reranking (Week 6)
    # ------------------------------------------------------------------
    print("\n[5/5] Full RAG pipeline (search + rerank + context formatting)...")

    retriever = RAGRetriever(search_engine=search_engine, reranker=reranker)
    rag_query = "syringe swap wrong drug dose error during surgery"
    ctx = retriever.retrieve(rag_query, top_k=5, rerank=True)

    print(f"\n  Query: \"{rag_query}\"")
    print(f"  Initial candidates: {len(ctx.results)}  |  After reranking: {len(ctx.reranked)}  |  Reranked: {ctx.was_reranked}")
    print("\n  -- RAG Context Block (paste into LLM prompt) ------------------")
    print(ctx.context_text)
    print("  --------------------------------------------------------------")

    print("\nOK Demo complete.\n")
    if not use_real_model:
        print("  Tip: run with --real-model to use the actual BGE-M3 + bge-reranker-large models.")
        print("  Real-model results will show true semantic similarity rather than hash-based vectors.\n")


if __name__ == "__main__":
    use_real = "--real-model" in sys.argv
    run_demo(use_real_model=use_real)
