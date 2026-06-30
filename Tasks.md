# AIR Clinical Incident Intelligence Engine - Tasks & Progress Tracking

**Version:** 1.0.0  
**Last Updated:** June 25, 2026  
**Current Phase:** Phase 5 - PDF & Advanced Features (Week 14 Complete, Phase 6 Next)

---

## Task Status Legend

- 📋 **NOT_STARTED** - Planned but not begun
- 🔄 **IN_PROGRESS** - Currently being worked on
- ✅ **COMPLETED** - Finished and validated
- ⏸️ **BLOCKED** - Waiting on dependencies
- 🔁 **REVIEW** - Awaiting code/domain review

---

## Phase 1: Data Foundation (Weeks 1-2)

### Week 1: Project Initialization & Excel Parsing

#### 1.1 Project Structure & Setup
- [x] **1.1.1** ✅ Create complete directory structure
- [x] **1.1.2** ✅ Initialize Git repository
- [x] **1.1.3** ✅ Create pyproject.toml with Poetry
- [x] **1.1.4** ✅ Install core dependencies
- [x] **1.1.5** ✅ Set up .env and configuration
- [x] **1.1.6** ✅ Create GitHub Actions CI/CD skeleton
- [x] **1.1.7** ✅ Write README.md with quick start

**Dependencies:**
```
pandas>=2.0.0
openpyxl>=3.10.0
pydantic>=2.0.0
python-dotenv>=1.0.0
pytest>=7.4.0
pytest-cov>=4.1.0
black>=23.0.0
ruff>=0.0.280
mypy>=1.4.0
```

#### 1.2 Data Models
- [x] **1.2.1** ✅ Design Incident model
- [x] **1.2.2** ✅ Design Patient model
- [x] **1.2.3** ✅ Design Surgery model
- [x] **1.2.4** ✅ Design Context model
- [x] **1.2.5** ✅ Design Outcome model
- [x] **1.2.6** ✅ Implement Pydantic validation
- [x] **1.2.7** ✅ Code review: models

**Location:** `src/models/incident.py`

#### 1.3 Excel Parsing Module
- [x] **1.3.1** ✅ Design parser architecture
- [x] **1.3.2** ✅ Implement column detection
- [x] **1.3.3** ✅ Implement row iteration
- [x] **1.3.4** ✅ Handle multiple sheets
- [x] **1.3.5** ✅ Implement error handling
- [x] **1.3.6** ✅ Create parser interface
- [x] **1.3.7** ✅ Code review: parser

**Location:** `src/ingestion/excel_parser.py`

#### 1.4 Testing & Validation
- [x] **1.4.1** ✅ Write unit tests for models
- [x] **1.4.2** ✅ Write unit tests for parser
- [x] **1.4.3** ✅ Create test fixtures
- [x] **1.4.4** ✅ Achieve >80% code coverage
- [x] **1.4.5** ✅ Test with sample Excel file
- [x] **1.4.6** ✅ Code review: tests

**Location:** `tests/unit/test_models.py`, `tests/unit/test_parsers.py`

#### 1.5 Documentation
- [x] **1.5.1** ✅ Write module docstrings
- [x] **1.5.2** ✅ Document all classes and functions
- [x] **1.5.3** ✅ Create Getting Started guide
- [x] **1.5.4** ✅ Document data model structure

---

### Week 2: Normalization Engine & Validation

#### 2.1 Normalization Engine
- [x] **2.1.1** ✅ Design normalization architecture
- [x] **2.1.2** ✅ Implement enum standardization
- [x] **2.1.3** ✅ Implement boolean normalization
- [x] **2.1.4** ✅ Implement date standardization
- [x] **2.1.5** ✅ Implement missing value handling
- [x] **2.1.6** ✅ Implement surgical taxonomy mapping
- [x] **2.1.7** 🔁 Code review: normalization

**Location:** `src/normalization/engine.py`, `src/normalization/mappers.py`

#### 2.2 Enums & Standards
- [x] **2.2.1** ✅ Define incident type taxonomy
- [x] **2.2.2** ✅ Define severity levels
- [x] **2.2.3** ✅ Define outcome categories
- [x] **2.2.4** ✅ Define surgical branches
- [x] **2.2.5** ✅ Define monitoring types

**Location:** `src/normalization/enums.py`

#### 2.3 Schema Validation
- [x] **2.3.1** ✅ Design validation strategy
- [x] **2.3.2** ✅ Create JSON schemas for validation
- [x] **2.3.3** ✅ Implement Pydantic validators
- [x] **2.3.4** ✅ Create validation error reporting
- [x] **2.3.5** 🔁 Code review: validation

**Location:** `src/ingestion/validators.py`

#### 2.4 AI Analysis Model
- [x] **2.4.1** ✅ Design AIAnalysis model
- [x] **2.4.2** ✅ Define output fields
- [x] **2.4.3** ✅ Create validation rules
- [x] **2.4.4** 🔁 Code review: AI model


**Location:** `src/models/analysis.py`

#### 2.5 Integration & Testing
- [x] **2.5.1** ✅ Write unit tests for normalization
- [x] **2.5.2** ✅ Write integration tests (parse → normalize)
- [x] **2.5.3** ✅ Test edge cases (missing, mixed types, invalid)
- [x] **2.5.4** ✅ Achieve >85% code coverage
- [x] **2.5.5** ✅ Validate output against Pydantic models

**Location:** `tests/unit/test_normalization.py`, `tests/integration/test_pipeline.py`

#### 2.6 Documentation
- [x] **2.6.1** ✅ Write Data Model Reference guide
- [x] **2.6.2** ✅ Document all enums
- [x] **2.6.3** ✅ Document normalization rules
- [x] **2.6.4** ✅ Document validation rules

---

## Phase 2: Core Intelligence (Weeks 3-5)

### Week 3: Incident Understanding Agent

#### 3.1 Clinical Understanding Agent
- [x] **3.1.1** ✅ Design LLM prompts and system instructions
- [x] **3.1.2** ✅ Implement incident understanding logic
- [x] **3.1.3** ✅ Create clinical reasoning framework
- [x] **3.1.4** ✅ Integrate LLM API (Claude Sonnet)
- [x] **3.1.5** ✅ Implement response parsing
- [x] **3.1.6** ✅ Create error handling for LLM calls

**Location:** `src/incident/understanding_agent.py`

**Depends on:** Phase 1 completion

#### 3.2 Multi-Label Classification
- [x] **3.2.1** ✅ Implement incident type classifier
- [x] **3.2.2** ✅ Create classification taxonomy
- [x] **3.2.3** ✅ Implement confidence scoring
- [x] **3.2.4** ✅ Create post-processing logic

**Location:** `src/incident/classifiers.py`

#### 3.3 Severity Analysis
- [x] **3.3.1** ✅ Design severity analysis logic
- [x] **3.3.2** ✅ Implement severity levels (Low/Moderate/High/Critical)
- [x] **3.3.3** ✅ Create severity scoring rules
- [x] **3.3.4** ✅ Integrate with incident understanding

**Location:** `src/incident/severity_analyzer.py`

#### 3.4 Testing & Validation
 - [x] **3.4.1** ✅ Write unit tests with mock LLM
 - [x] **3.4.2** ✅ Write integration tests with real LLM (guarded)
 - [x] **3.4.3** ✅ Validate taxonomy consistency
 - [~] **3.4.4** 🔄 Domain expert review script created (awaiting review)
 - [ ] **3.4.5** ⏸️ Achieve >80% domain expert agreement

---

### Week 4: Validation Layer & Root Cause Analysis

**Status Update (May 22, 2026):** Persistence scaffold (opt-in) created; validation agent, retry logic, reporting, output constraints, and RCA are now in place for Week 4.

#### 4.1 Validation Agent
- [x] **4.1.1** ✅ Design validation logic
- [x] **4.1.2** ✅ Implement contradiction detection
- [x] **4.1.3** ✅ Create JSON schema validation
- [x] **4.1.4** ✅ Implement retry logic
- [x] **4.1.5** ✅ Create validation reporting

**Location:** `src/validation/validator_agent.py`

#### 4.2 Validation Rules
- [x] **4.2.1** ✅ Define contradiction rules
- [x] **4.2.2** ✅ Define required field rules
- [x] **4.2.3** ✅ Define confidence thresholds
- [x] **4.2.4** ✅ Define output constraints

**Location:** `src/validation/schemas.py`

#### 4.3 Root Cause Analysis
- [x] **4.3.1** ✅ Design RCA framework
- [x] **4.3.2** ✅ Implement systemic failure detection
- [x] **4.3.3** ✅ Create contributing factor analysis
- [x] **4.3.4** ✅ Implement learning generation

**Location:** `src/incident/root_cause_analyzer.py`

#### 4.4 Testing & Validation
- [x] **4.4.1** ✅ Unit tests for validation logic
- [x] **4.4.2** ✅ Test contradiction detection
- [x] **4.4.3** ✅ Validate zero hallucination rate
- [x] **4.4.4** ✅ Integration tests with full pipeline

---

### Week 5: Embedding Generation & Vector Integration

**Status Update (June 6, 2026):** Week 5 complete. 53 new tests added. Full pipeline operational.
**Manual Validation (June 6, 2026):** Validated via Postman against live FastAPI server. `POST /retrieval/ingest/excel` successfully embeds and stores incidents. `POST /retrieval/search` and `POST /retrieval/rag` return results with metadata. Confirmed metadata fallback works correctly when incidents are ingested without AI analysis.

#### 5.1 Embedding Engine
- [x] **5.1.1** ✅ Design embedding architecture (lazy-load, batch, text builder)
- [x] **5.1.2** ✅ Integrate BGE-M3 model (via sentence-transformers, 1024-dim)
- [x] **5.1.3** ✅ Implement batch embedding (embed_batch, embed_incidents_batch)
- [x] **5.1.4** ✅ Create error handling (ImportError, dimension mismatch)
- [x] **5.1.5** ✅ Implement caching mechanism (lazy model load; model injected in tests)

**Location:** `src/embeddings/engine.py`, `src/embeddings/models.py`

#### 5.2 Vector Store Integration
- [x] **5.2.1** ✅ Design Qdrant integration (QdrantHandler with injected client)
- [x] **5.2.2** ✅ Implement collection creation (ensure_collection, idempotent)
- [x] **5.2.3** ✅ Implement vector insertion (upsert single + batch)
- [x] **5.2.4** ✅ Create metadata handling (VectorMetadata → Qdrant payload)
- [x] **5.2.5** ✅ Implement batch operations (upsert_batch in single Qdrant call)

**Location:** `src/vector_store/qdrant_handler.py`

#### 5.3 Metadata Management
- [x] **5.3.1** ✅ Design metadata schema (VectorMetadata model already existed)
- [x] **5.3.2** ✅ Implement metadata extraction (extract_metadata with analysis fallback)
- [x] **5.3.3** ✅ Create metadata indexing (build_payload → Qdrant payload dict)
- [x] **5.3.4** ✅ Implement filtering logic (search() accepts {field: value} filters)

**Location:** `src/vector_store/metadata.py`

#### 5.4 Integration Testing
- [x] **5.4.1** ✅ End-to-end pipeline test (8 integration tests, in-memory Qdrant)
- [x] **5.4.2** ✅ Performance benchmarking (all 53 tests complete in <2s)
- [x] **5.4.3** ✅ Query validation (exact vector → cosine score > 0.99)
- [x] **5.4.4** ✅ Scalability design (batch upsert; engine handles empty list gracefully)

---

## Phase 3: Retrieval & Discovery (Weeks 6-8)

### Week 6: Similarity Search & Retrieval

#### 6.1 Similarity Search
- [x] **6.1.1** ✅ Design search architecture
- [x] **6.1.2** ✅ Implement vector similarity search (search_by_text, search_by_incident, search_by_vector)
- [x] **6.1.3** ✅ Create metadata filtering (severity, surgery_type, year, incident_type array-contains)
- [x] **6.1.4** ✅ Implement Top-K selection (ranked SimilaritySearchResult with 1-based rank)
- [x] **6.1.5** ✅ Create search interface (search_similar_to_stored uses stored vector, no re-embed)

**Location:** `src/retrieval/similarity_search.py`

#### 6.2 Reranking
- [x] **6.2.1** ✅ Integrate bge-reranker-large (CrossEncoderReranker with lazy load)
- [x] **6.2.2** ✅ Implement reranking logic (CrossEncoder.rank() → RerankResult ordered by score)
- [x] **6.2.3** ✅ Create relevance scoring (rerank_score preserved alongside original similarity_score)
- [x] **6.2.4** ✅ Implement threshold filtering (configurable min_score via threshold param)

**Location:** `src/retrieval/reranker.py`

#### 6.3 RAG Retrieval
- [x] **6.3.1** ✅ Design RAG architecture (RAGRetriever wraps SimilaritySearchEngine + reranker)
- [x] **6.3.2** ✅ Implement retrieval pipeline (retrieve(), retrieve_for_incident(), from_components())
- [x] **6.3.3** ✅ Create context formatting (format_context() → plain text, LLM-injectable)
- [x] **6.3.4** ✅ Implement source attribution (incident_id, similarity_score/rerank_score in output)

**Location:** `src/retrieval/rag.py`

#### 6.4 Testing & Validation
- [ ] **6.4.1** ⏸️ Clinician validation of retrieval (domain expert review pending)
- [x] **6.4.2** ✅ Manual Postman validation (June 6 + June 8, 2026): all 6 endpoints verified live
- [x] **6.4.3** ✅ Performance: search returns in <100ms (in-memory Qdrant); response shape confirmed
- [x] **6.4.4** ✅ Integration tests (73 new tests: 24+14+23 unit + 12 integration; 212 passing total)

#### 6.5 Post-Week Additions (June 8, 2026)
- [x] **6.5.1** ✅ `POST /retrieval/ingest/analyzed` endpoint — accepts `{"incidents": [...], "analyses": [...]}`, matches by incident_id
- [x] **6.5.2** ✅ `VectorMetadata.key_learning` field added to schema; populated from `AIAnalysis.key_learning` in `extract_metadata()`
- [x] **6.5.3** ✅ `scripts/demo_retrieval.py` created — 8 clinical incidents, offline fake models, 5-phase demo

**Manual Postman Results (June 6, 2026):**
- `GET /retrieval/status` — returns embedding model name + collection stats OK
- `POST /retrieval/ingest` (JSON) — `ingested: 1`, correct incident_id returned OK
- `POST /retrieval/ingest/excel` — parses Log.xlsx, embeds all incidents, returns count OK
- `POST /retrieval/search` with `severity: "Critical"` — `filters_applied: true`, returns only Critical incidents OK
- `POST /retrieval/search/similar` — returns 2 similar incidents with rank + cosine score OK
- `POST /retrieval/rag` — returns `context_text` block with query header + numbered incidents + scores OK
- Metadata fallback confirmed: Excel incidents without AI analysis show `severity: "Unknown"` (expected)

**Additional Postman Results (June 8, 2026):**
- `POST /retrieval/ingest/analyzed` — `{"incidents": [...], "analyses": [...]}` → `ingested: 1`, rich metadata stored OK
- `POST /retrieval/search` after analyzed ingest — `key_learning` field populated in results OK
- `POST /retrieval/rag` after analyzed ingest — "Key learning:" line present in `context_text` OK

---

### Week 7: Theme Clustering

**Status Update (June 8, 2026):** Week 7 complete. 81 new tests added. Full clustering pipeline operational.
**Manual E2E Testing (June 13, 2026):** All clustering endpoints validated against `AIR_Log_Report_Merged.xlsx`. 4 clusters found with min_cluster_size=2, silhouette=0.276. UMAP coords valid. min_cluster_size=3 confirmed too large for 10-incident dataset (yields 0 clusters) — Postman collection corrected.

#### 7.1 Clustering Engine
- [x] **7.1.1** ✅ Implement HDBSCAN clustering (`IncidentClusteringEngine._run_hdbscan`, injectable model)
- [x] **7.1.2** ✅ Create dimensionality reduction (`_reduce_dimensions` 10D + `_reduce_to_2d` 2D viz)
- [x] **7.1.3** ✅ Implement clustering quality metrics (silhouette score via sklearn; None when <2 clusters)
- [x] **7.1.4** ✅ Create cluster validation (`ClusteringResult.is_meaningful`; all incident IDs accounted for)

**Location:** `src/retrieval/clustering.py`

#### 7.2 Theme Extraction
- [x] **7.2.1** ✅ Implement theme naming — LLM (ChatAnthropic via LangChain) + keyword fallback (`ThemeExtractor`)
- [x] **7.2.2** ✅ Create pattern extraction (`extract_patterns`, `most_common_values`, `extract_root_cause_keywords`)
- [x] **7.2.3** ✅ Implement theme summarization (`ClusteringResult.summary_report()` plain-text)
- [x] **7.2.4** ✅ Create recommendation generation (`fallback_recommendations` + LLM path)

**Location:** `src/retrieval/theme_extractor.py`, `src/retrieval/clustering.py`

#### 7.3 Visualization
- [x] **7.3.1** ✅ UMAP 2D visualisation coordinates (`ClusteringResult.umap_coords`: [{incident_id, x, y, cluster_id}])
- [x] **7.3.2** ✅ Theme summary reports (`summary_report()` — plain text, suitable for display or LLM injection)
- [ ] **7.3.3** ⏸️ Interactive exploration (optional — deferred to frontend phase)

#### 7.4 Testing & Validation
- [ ] **7.4.1** ⏸️ Clinician validation of themes (domain expert review pending)
- [x] **7.4.2** ✅ Quality metrics: silhouette score computed; noise_ratio tracked; theme IDs unique
- [x] **7.4.3** ✅ Integration tests: 16 tests covering scroll_all + full cluster pipeline (test_week7_clustering_pipeline.py)
- [x] **7.4.4** ✅ Manual Postman E2E testing (June 13, 2026): `POST /retrieval/cluster` validated against real Excel data — 4 clusters, 1 noise, silhouette=0.276, UMAP coords verified
- [ ] **7.4.5** ⏸️ Scalability testing (10k+ incidents — deferred; in-memory Qdrant suitable for current scale)

#### 7.5 Infrastructure
- [x] **7.5.1** ✅ `QdrantHandler.scroll_all()` — paginated fetch of all vectors (batches of 100)
- [x] **7.5.2** ✅ `POST /retrieval/cluster` API endpoint — ClusterRequest (min_cluster_size, use_llm_naming) + ClusterResponse
- [x] **7.5.3** ✅ `src/retrieval/__init__.py` updated with Week 7 exports

**Test counts (June 8, 2026):**
- `tests/unit/test_week7_clustering.py` — 48 tests (ClusteringResult, IncidentClusteringEngine, pattern helpers)
- `tests/unit/test_week7_theme_extractor.py` — 20 tests (fallback, LLM path, LLM failure, _summarise_for_llm)
- `tests/integration/test_week7_clustering_pipeline.py` — 16 tests (scroll_all + full pipeline)
- **Total Week 7: 81 new tests | Grand total: 293 passing, 86% coverage**

---

### Week 8: RAG Integration

**Status Update (June 12, 2026):** Week 8 complete. 111 new tests added. Full grounded RAG pipeline operational.
**Manual E2E Testing (June 13, 2026):** All 8 retrieval endpoint stages validated against `AIR_Log_Report_Merged.xlsx` (10 real incidents). All endpoints pass. Intent classification, coverage scoring, citations, and grounded_context all correct. Confidence="Insufficient" for quick-path data confirmed as expected (sparse metadata → coverage=0.0). Rich metadata path (Stage 8) chains correctly end-to-end.

#### 8.1 RAG Pipeline
- [x] **8.1.1** ✅ Extend `src/retrieval/rag.py` with `GroundedRAGPipeline` and `GroundedRetrievalResult`
- [x] **8.1.2** ✅ Implement query preprocessing (`src/retrieval/query_preprocessor.py`) — intent, keywords, filter inference, synonym expansion
- [x] **8.1.3** ✅ Create context aggregation (EvidenceTracker.format_grounded_context — per-item grading + coverage summary)
- [x] **8.1.4** ✅ Implement result formatting (grounded_context with grade markers + citation, context_text for backward compat)

**Location:** `src/retrieval/rag.py`, `src/retrieval/query_preprocessor.py`

#### 8.2 Evidence Tracking
- [x] **8.2.1** ✅ Design evidence attribution system (`EvidenceBundle` + `EvidenceItem` dataclasses)
- [x] **8.2.2** ✅ Implement source tracking (`EvidenceTracker.build_bundle` — processes any result type)
- [x] **8.2.3** ✅ Create citation formatting (`_build_citation` — incident_id, severity, type, score)
- [x] **8.2.4** ✅ Implement confidence scoring (High/Moderate/Low/Insufficient from grade distribution + coverage)

**Location:** `src/retrieval/evidence.py`

#### 8.3 Quality Assurance
- [x] **8.3.1** ✅ Grounding effectiveness: coverage_score measures keyword overlap with retrieved metadata
- [x] **8.3.2** ✅ Evidence relevance: High/Moderate/Low grading by score thresholds (0.75 / 0.50)
- [x] **8.3.3** ✅ Confidence derived: High requires >=2 High-grade results + >=60% coverage
- [x] **8.3.4** ✅ Performance: all 111 tests complete in <30s (no model downloads, in-memory Qdrant)

#### 8.4 Integration Testing
- [x] **8.4.1** ✅ End-to-end RAG tests: `tests/integration/test_week8_rag_pipeline.py` (16 tests)
- [x] **8.4.2** ✅ Filter inference validated: severity filter auto-inferred from query text
- [x] **8.4.3** ✅ Quality metric validation: coverage_score, confidence, high_relevance_count in response

#### 8.5 Manual Postman E2E Validation (June 13, 2026)
- [x] **8.5.1** ✅ All 5 intent variants tested: general/root_cause/pattern_analysis/safety_recommendations/similar_incidents — all correctly classified against real Excel data
- [x] **8.5.2** ✅ Keyword extraction and clinical synonym expansion verified (anaesthesia → anesthesia/anesthetic/anaesthetic)
- [x] **8.5.3** ✅ Citations format verified: `"Incident {id[:12]} | severity=... | type=... | score=..."` present in all responses
- [x] **8.5.4** ✅ Bypass path (`use_preprocessing: false`) verified: `suggested_filters: null`, `coverage_score: 1.0`
- [x] **8.5.5** ✅ Confidence behaviour documented: "Insufficient" is correct with quick-path (no AI analysis) metadata; resolves to Moderate/High after Stage 8 rich path
- [x] **8.5.6** ✅ Full Stage 8 rich path validated: Parse → Analyze → Ingest/Analyzed chains correctly, 10 incidents with AI-enriched metadata (incident_type populated, severity set, root_cause text in metadata)

**Location:** `src/api/retrieval.py` — `POST /retrieval/rag/grounded` endpoint

**Test counts (June 12, 2026):**
- `tests/unit/test_week8_query_preprocessor.py` — 36 tests (intent, keywords, filter inference, expansion, custom injection)
- `tests/unit/test_week8_evidence.py` — 24 tests (grading, citations, coverage, confidence, bundle properties)
- `tests/unit/test_week8_grounded_rag.py` — 20 tests (GroundedRetrievalResult, pipeline init, retrieve, factory)
- `tests/integration/test_week8_rag_pipeline.py` — 16 tests (empty store, with data, filter inference, result structure)
- **Total Week 8: 111 new tests | Grand total: 404 passing, 1 skipped, 86% coverage**

---

## Phase 4: Insight Generation (Weeks 9-11)

### Week 9: Insight Generation Agent | ✅ Complete (June 13, 2026)

#### 9.1 Insight Generator
- [x] **9.1.1** ✅ Design insight generation system — InsightGenerator with ChatAnthropic + with_structured_output(InsightLLMResponse)
- [x] **9.1.2** ✅ Implement contextual analysis — generate() accepts grounded_context; generate_from_result() wraps GroundedRetrievalResult
- [x] **9.1.3** ✅ Create pattern connection logic — prompt enforces connecting incidents, quantifying patterns
- [x] **9.1.4** ✅ Implement safety recommendations — actionable_steps require actor + action; is_actionable requires 2+ steps
- [x] **9.1.5** ✅ Create evidence grounding — citation constraint in prompt; all citations from EvidenceBundle.citations

**Location:** `src/insights/generator.py`, `src/insights/models.py`

#### 9.2 Prompt Engineering
- [x] **9.2.1** ✅ Design system prompts — APSA-quality SYSTEM_PROMPT with 5 mandatory rules and JSON output spec
- [x] **9.2.2** ✅ Create few-shot examples — BAD/GOOD contrast in system prompt (vague vs specific mechanism)
- [x] **9.2.3** ✅ Implement context injection — build_user_message() injects query, intent guidance, citation block, grounded context
- [x] **9.2.4** ✅ Test prompt variations — 5 intent-specific guidance blocks (root_cause/pattern_analysis/safety_recommendations/similar_incidents/general)

**Location:** `src/insights/prompts.py`

#### 9.3 Quality Assurance
- [x] **9.3.1** ✅ Domain expert review framework — specificity_score (0.0-1.0) on each GeneratedInsight
- [x] **9.3.2** ✅ Measure insight specificity — is_grounded (citations present), specificity_score heuristic
- [x] **9.3.3** ✅ Validate actionability — is_actionable (actionable_steps >= 2); actionable_count on InsightBatch
- [x] **9.3.4** ✅ Create quality metrics — batch: grounded_count, actionable_count, generation_confidence rollup

#### 9.4 Testing
- [x] **9.4.1** ✅ Unit tests for models — 24 tests (InsightItem, LLMResponse, GeneratedInsight, InsightBatch properties)
- [x] **9.4.2** ✅ Unit tests for InsightGenerator — 30 tests (init, fallback, empty, LLM path, specificity, confidence, parse, delegation)
- [x] **9.4.3** ✅ Integration tests — 15 tests (pipeline, fallback, prompt builder, API serialisation)
- [x] **9.4.4** ✅ 91 total Week 9 tests, all passing

#### 9.5 API Endpoints
- [x] **9.5.1** ✅ `GET /insights/status` — LLM availability and model info
- [x] **9.5.2** ✅ `POST /insights/generate` — insights from pre-retrieved grounded context
- [x] **9.5.3** ✅ `POST /insights/from_query` — full pipeline (GroundedRAGPipeline -> InsightGenerator)
- [x] **9.5.4** ✅ `src/api/main.py` updated with insights router

---

### Week 10: Editorial Intelligence Layer | ✅ Complete (June 13, 2026)

#### 10.1 Editorial Engine
- [x] **10.1.1** ✅ Design editorial system — ThemeGrouper + ToneValidator + NarrativeBuilder + EditorialEngine
- [x] **10.1.2** ✅ Implement APSA-style narrative generation — single LLM call for full report (all sections + executive summary + conclusion)
- [x] **10.1.3** ✅ Create thematic commentary — ThemeGrouper canonical order; per-theme guidance blocks in prompt
- [x] **10.1.4** ✅ Implement tone adjustment — ToneValidator with 28 forbidden phrases; tone_score (0.0-1.0) on each section and report
- [x] **10.1.5** ✅ Create quality assurance — insight_count, is_grounded, word_count per section; grounded_section_count on report

**Location:** `src/insights/editorial.py`, `src/insights/editorial_models.py`

#### 10.2 Style & Tone
- [x] **10.2.1** ✅ Define tone guidelines — TONE REQUIREMENTS block in EDITORIAL_SYSTEM_PROMPT
- [x] **10.2.2** ✅ Create APSA examples collection — BAD/GOOD narrative examples embedded in system prompt
- [x] **10.2.3** ✅ Implement style enforcement — FORBIDDEN LANGUAGE block (28 phrases) + ToneValidator runtime check
- [x] **10.2.4** ✅ Create quality checking — ToneValidator.validate() returns (score, found_phrases) deterministically

**Location:** `src/insights/editorial_prompts.py`

#### 10.3 Editorial Workflow
- [x] **10.3.1** ✅ Design multi-stage workflow — InsightBatch -> ThemeGrouper -> NarrativeBuilder -> ToneValidator -> EditorialReport
- [x] **10.3.2** ✅ Implement theme grouping — ThemeGrouper._SECTION_ORDER (root_cause -> pattern_analysis -> safety_recommendations -> general)
- [x] **10.3.3** ✅ Create narrative generation — NarrativeBuilder.build_report() generates full cohesive report in one call
- [x] **10.3.4** ✅ Implement quality review — tone_score on each section; flagged phrases logged as warnings

#### 10.4 Testing & Validation
- [x] **10.4.1** ✅ Editorial model tests — 27 tests (SectionLLMItem, EditorialLLMResponse, EditorialSection, EditorialReport properties)
- [x] **10.4.2** ✅ Engine component tests — 35 tests (ThemeGrouper, ToneValidator, NarrativeBuilder, EditorialEngine with fake LLM)
- [x] **10.4.3** ✅ Integration tests — 24 tests (full pipeline, fallback, prompt builder, API serialisation)
- [x] **10.4.4** ✅ 86 total Week 10 tests, all passing

#### 10.5 API Endpoints
- [x] **10.5.1** ✅ `GET /editorial/status` — LLM availability and model info
- [x] **10.5.2** ✅ `POST /editorial/generate` — editorial report from InsightBatchOut JSON
- [x] **10.5.3** ✅ `POST /editorial/from_query` — full pipeline (GroundedRAGPipeline -> InsightGenerator -> EditorialEngine)
- [x] **10.5.4** ✅ `src/api/main.py` updated with editorial router

---

### Week 11: Output Formatting & Integration

#### 11.1 Output Formatters
- [x] **11.1.1** ✅ Design output architecture — stateless formatter classes accepting EditorialReport
- [x] **11.1.2** ✅ Implement JSON formatter — already handled by existing API serialisation (_report_to_out)
- [x] **11.1.3** ✅ Implement Markdown formatter — MarkdownFormatter (title, exec summary, sections, conclusion, evidence refs, footer)
- [x] **11.1.4** ✅ Implement Excel formatter — ExcelFormatter (Summary sheet + per-section sheets + Citations sheet)
- [x] **11.1.5** ✅ Create custom report templates — APSA-style layout embedded in formatters

**Location:** `src/insights/formatters.py`

#### 11.2 Output Schemas
- [x] **11.2.1** ✅ Define JSON schema — existing EditorialReportOut Pydantic model covers this
- [x] **11.2.2** ✅ Define Markdown templates — APSA newsletter structure in MarkdownFormatter
- [x] **11.2.3** ✅ Define Excel layouts — Summary + section sheets + Citations in ExcelFormatter
- [x] **11.2.4** ✅ Create validation rules — sheet name max-31-char sanitisation; missing section/citation graceful handling

#### 11.3 End-to-End Integration
- [x] **11.3.1** ✅ Implement full pipeline — POST /pipeline/report (query → retrieve → insights → editorial → format)
- [x] **11.3.2** ✅ Create error handling — stage-labelled HTTPException with logger.exception per stage
- [x] **11.3.3** ✅ Implement progress tracking — pipeline_stages list in PipelineReportResponse
- [x] **11.3.4** ✅ Create batch processing — POST /pipeline/ingest handles N incidents in one call

#### 11.4 Testing & Validation
- [x] **11.4.1** ✅ Format validation tests — 35 unit tests (MarkdownFormatter + ExcelFormatter)
- [x] **11.4.2** ✅ Data integrity tests — Excel round-trip, base64 round-trip, sheet content assertions
- [x] **11.4.3** ✅ End-to-end pipeline tests — 24 integration tests (format chain + API model validation)
- [x] **11.4.4** ✅ >90% success rate validation — 650/651 tests passing (650 pass, 1 skip)

#### 11.5 APSA Format Alignment & Newsletter (June 25, 2026)
- [x] **11.5.1** ✅ APSA-aligned MarkdownFormatter — evocative title, flowing prose, no Key Learning blocks, academic references
- [x] **11.5.2** ✅ `evocative_title` + `clinical_references` added to `EditorialLLMResponse` and `EditorialReport`
- [x] **11.5.3** ✅ Updated `EDITORIAL_SYSTEM_PROMPT` — requests journalistic title + Vancouver-format academic references
- [x] **11.5.4** ✅ `APSA_INCIDENT_SYSTEM_PROMPT` — per-incident newsletter article (vignette + educational body + references)
- [x] **11.5.5** ✅ `IncidentEditorialEngine` — generates one `APSAArticle` per incident from Qdrant metadata
- [x] **11.5.6** ✅ `APSANewsletterFormatter` — bundles N articles into one newsletter Markdown document
- [x] **11.5.7** ✅ `POST /pipeline/newsletter` — top-k incidents by severity → per-incident APSA articles → newsletter

---

## Phase 5: PDF & Advanced Features (Weeks 12-14)

### Week 12: PDF Ingestion Module ✅ Complete (June 25, 2026)

#### 12.1 PDF Parser
- [x] **12.1.1** ✅ Design PDF parsing architecture — PDFParser class with pdfplumber extraction + fix_doubled_chars deduplication
- [x] **12.1.2** ✅ Implement doubled-character artifact fix — `fix_doubled_chars()` handles all form field encoding artifacts
- [x] **12.1.3** ✅ Implement section detection — regex-based section header splitting into named sections dict
- [x] **12.1.4** ✅ Implement field extraction helpers — `_field()`, `_float_field()`, `_outcome_category()`, `_primary_technique()`, etc.
- [x] **12.1.5** ✅ Create field → Incident model mapping — `_build_incident()` maps all PDF sections to Incident sub-models

**Location:** `src/ingestion/pdf_parser.py`

#### 12.2 Document Processing
- [x] **12.2.1** ✅ Implement document validation — file existence + extension check; empty text warning
- [x] **12.2.2** ✅ Implement date extraction from filename — `_AIRLog_YYYYMMDD_` pattern → `metadata.month` + `metadata.year`
- [x] **12.2.3** ✅ Implement harm severity mapping — outcome category letter (A-I) → Low/Moderate/High/Critical/None
- [x] **12.2.4** ✅ Implement directory batch parsing — `parse_directory()` with per-file error handling

#### 12.3 API Endpoint
- [x] **12.3.1** ✅ `POST /pipeline/ingest/pdf` — upload single PDF → parse → optional AI analysis → Qdrant upsert
- [x] **12.3.2** ✅ `PDFIngestResult` response model — ingested, analyzed, failed_analysis, incident_ids, collection, dimension, note

#### 12.4 Testing & Validation
- [x] **12.4.1** ✅ Unit tests — 96 tests covering fix_doubled_chars, harm severity, section parsing, all field helpers, build_incident, error handling
- [x] **12.4.2** ✅ Integration tests — 37 tests with all 3 real PDFs (110939, 111045, 111120); directory parsing; pipeline model validation
- [x] **12.4.3** ✅ All 783 tests passing (133 new, 0 regressions)

**Test counts (June 25, 2026):**
- `tests/unit/test_week12_pdf_parser.py` — 96 tests
- `tests/integration/test_week12_pdf_pipeline.py` — 37 tests
- **Total Week 12: 133 new tests | Grand total: 783 passing, 1 skipped, 81% coverage**

---

### Week 13: Multi-Source RAG ✅ COMPLETE

#### 13.1 Multi-Document Retrieval
- [x] **13.1.1** ✅ `VectorMetadata` extended with `source_type` (default `"incident_report"`) and `title` fields — backward-compatible
- [x] **13.1.2** ✅ `SearchFilters.source_type` filter added — `to_qdrant_filter()` emits `FieldCondition` for it
- [x] **13.1.3** ✅ Single-collection multi-source design: incidents + literature share `incidents` Qdrant collection
- [x] **13.1.4** ✅ `POST /retrieval/trends` — temporal analytics with source_type breakdown per bucket

#### 13.2 Literature Integration
- [x] **13.2.1** ✅ `src/models/literature.py` — `LiteratureDocument` dataclass with `create()`, `embeddable_text`, `citation_string`
- [x] **13.2.2** ✅ `src/ingestion/literature_parser.py` — `LiteratureParser` with `parse_text()`, `parse_pdf()`, `parse_json_batch()`
- [x] **13.2.3** ✅ `extract_literature_metadata()` in `src/vector_store/metadata.py` — maps docs to `VectorMetadata`
- [x] **13.2.4** ✅ `POST /retrieval/ingest/literature` — JSON batch ingest with embed + Qdrant upsert; `EmbeddingEngine.embed_document()` added

#### 13.3 Testing & Validation
- [x] **13.3.1** ✅ `tests/unit/test_week13_literature.py` — 54 unit tests (LiteratureDocument, LiteratureParser, extract_literature_metadata, SearchFilters, VectorMetadata backward-compat)
- [x] **13.3.2** ✅ `tests/integration/test_week13_cross_source.py` — 35 integration tests (cross-source ingestion, source_type filter, combined filters, trends aggregation, Qdrant payload validation)
- [x] **13.3.3** ✅ All 89 Week 13 tests passing (54 unit + 35 integration)
- [x] **13.3.4** ✅ Pydantic model tests: `LiteratureIngestResult`, `TrendBucket`, `TrendsResponse`

---

### Week 14: Advanced Clustering & Analytics ✅ COMPLETE

#### 14.1 Advanced Clustering
- [x] **14.1.1** ✅ Auto-param tuning in `IncidentClusteringEngine` — `auto_params=True` sets `min_cluster_size = max(3, sqrt(n))` and `min_samples = min_cluster_size - 1`; exposed via `ClusterRequest.auto_params`
- [x] **14.1.2** ✅ HDBSCAN noise-point labelling leveraged as anomaly signal — noise points (label=-1) represent incidents whose feature combination matches no peer cluster
- [x] **14.1.3** ✅ Outlier scores from `hdbscan.HDBSCAN(prediction_data=True).outlier_scores_` attached to each anomaly result
- [x] **14.1.4** ✅ `src/retrieval/anomaly_detector.py` — `AnomalyDetector` + `AnomalyResult` + `AnomalyDetectionResult`; `POST /retrieval/anomalies` endpoint

#### 14.2 Analytics & Insights
- [x] **14.2.1** ✅ Per-period severity distribution and dominant incident types in `PeriodStats`
- [x] **14.2.2** ✅ `src/retrieval/pattern_analyzer.py` — `PatternAnalyzer` with full temporal analysis
- [x] **14.2.3** ✅ Trend detection: increasing / decreasing / stable; acceleration: accelerating / decelerating / stable; most volatile incident type by count variance
- [x] **14.2.4** ✅ `POST /retrieval/patterns` endpoint — month-over-month rate change, severity weight trend, one-sentence insight; literature auto-excluded

#### 14.3 Performance Optimization
- [x] **14.3.1** ✅ Auto-params heuristic reduces over-clustering on large datasets without manual tuning
- [x] **14.3.2** ✅ PatternAnalyzer is pure Python (no ML) — runs in O(n) with no model loading
- [ ] **14.3.3** ⏸️ Embedding cache — deferred to Phase 6 (incidents are unique; cache hit rate low)
- [ ] **14.3.4** ⏸️ Batch embedding optimisation — existing `embed_incidents_batch()` already handles this

#### 14.4 Testing & Validation
- [x] **14.4.1** ✅ `tests/unit/test_week14_analytics.py` — 40 unit tests (AnomalyDetector, PatternAnalyzer, auto_params, Pydantic models)
- [x] **14.4.2** ✅ `tests/integration/test_week14_advanced_clustering.py` — 18 integration tests (in-memory Qdrant, fake embeddings, literature exclusion)
- [x] **14.4.3** ✅ All 58 Week 14 tests passing
- [ ] **14.4.4** ⏸️ Scalability tests (10k+ incidents) — deferred to Phase 6 load testing

---

## Phase 6: Production Readiness (Weeks 15-16)

### Week 15: Hardening, Docker & Performance

#### 15.1 FastAPI Application (already built — hardening only)
- [x] **15.1.1** ✅ FastAPI app created — `src/api/main.py` with all routers (built Week 1)
- [x] **15.1.2** ✅ Request/response models — Pydantic v2 throughout all API routers (built Weeks 1-12)
- [x] **15.1.3** ✅ Error handling — per-stage HTTPException with logger.exception in all endpoints (built Week 11)
- [x] **15.1.4** ✅ Structured logging — `get_logger()` in every module (built Week 1)
- [ ] **15.1.5** ⏸️ Authentication (optional) — API key header middleware if required

#### 15.2 API Completeness Audit
- [x] **15.2.1** ✅ Ingestion: POST /incidents/ingest, /ingest/excel, /ingest/analyzed; POST /pipeline/ingest, /pipeline/ingest/pdf
- [x] **15.2.2** ✅ Analysis: POST /incidents/analyze, /incidents/analyze/excel
- [x] **15.2.3** ✅ Search: POST /retrieval/search, /search/similar, /rag, /rag/grounded, /cluster
- [x] **15.2.4** ✅ Intelligence: POST /insights/generate, /from_query; POST /editorial/generate, /from_query
- [x] **15.2.5** ✅ Pipeline: GET /pipeline/status; POST /pipeline/report, /pipeline/newsletter
- [x] **15.2.6** ✅ Status: GET /retrieval/status, /insights/status, /editorial/status
- [ ] **15.2.7** ⏸️ GET /health — root health check endpoint (quick win, add to main.py)

#### 15.3 Docker & Deployment
- [ ] **15.3.1** ⏸️ Dockerfile — Python 3.11 slim + poetry install + uvicorn entrypoint
- [ ] **15.3.2** ⏸️ docker-compose.yml — app + qdrant service (persistent volume)
- [ ] **15.3.3** ⏸️ .dockerignore + environment variable documentation
- [ ] **15.3.4** ⏸️ Startup healthcheck script

#### 15.4 Testing & Coverage
- [x] **15.4.1** ✅ Unit tests — 783 passing across all modules (built Weeks 1-12)
- [x] **15.4.2** ✅ Integration tests — all pipeline stages covered with real PDFs + Excel files
- [ ] **15.4.3** ⏸️ Achieve ≥85% coverage (currently 81%)
- [ ] **15.4.4** ⏸️ Load/stress test — concurrent requests to /pipeline/report

#### 15.5 Security & Performance
- [x] **15.5.1** ✅ Input validation — Pydantic v2 strict validation on all request models
- [ ] **15.5.2** ⏸️ CORS settings — configure allowed origins in main.py
- [ ] **15.5.3** ⏸️ Rate limiting — slowapi or custom middleware
- [ ] **15.5.4** ⏸️ Response time profiling — identify bottlenecks (embedding load, LLM calls)

---

### Week 16: Documentation & Deployment Readiness

#### 16.1 Documentation
- [x] **16.1.1** ✅ OpenAPI/Swagger — auto-generated at `/docs` by FastAPI (available now)
- [ ] **16.1.2** ⏸️ Architecture document — data flow diagram + component overview
- [ ] **16.1.3** ⏸️ Deployment guide — Docker setup, env vars, Qdrant persistence
- [ ] **16.1.4** ⏸️ API reference — endpoint-by-endpoint usage examples
- [ ] **16.1.5** ⏸️ Troubleshooting guide — common errors, fallback modes

#### 16.2 Deployment Preparation
- [ ] **16.2.1** ⏸️ Docker image build + smoke test
- [ ] **16.2.2** ⏸️ Qdrant persistent-volume test (restart → data preserved)
- [ ] **16.2.3** ⏸️ .env.example audit — all required vars documented
- [ ] **16.2.4** ⏸️ End-to-end deployment test: Docker up → ingest PDFs → generate newsletter

#### 16.3 Final Validation
- [ ] **16.3.1** ⏸️ Full E2E test: 3 PDFs + Excel → pipeline/report + newsletter
- [ ] **16.3.2** ⏸️ Fallback-mode validation: all endpoints functional without ANTHROPIC_API_KEY
- [ ] **16.3.3** ⏸️ APSA editorial quality review — spot-check 3 generated articles for format compliance
- [ ] **16.3.4** ⏸️ Data integrity — re-ingest same file, verify no duplicate incidents

#### 16.4 Handoff
- [ ] **16.4.1** ⏸️ QUICKSTART.md — Docker up + first ingest + first newsletter in ≤5 steps
- [ ] **16.4.2** ⏸️ Update README.md — full feature list, architecture overview, API summary
- [ ] **16.4.3** ⏸️ Final git tag v1.0.0
- [ ] **16.4.4** ⏸️ Launch to production

---

## Cross-Phase Tasks

### Code Quality (Continuous)
- [ ] **CQ.1** 🔄 Type hints on all code (ongoing)
- [ ] **CQ.2** 🔄 Docstrings for all modules (ongoing)
- [ ] **CQ.3** 🔄 Code review before merge (ongoing)
- [ ] **CQ.4** 🔄 Linting with Ruff (ongoing)
- [ ] **CQ.5** 🔄 Formatting with Black (ongoing)
- [ ] **CQ.6** 🔄 Type checking with mypy (ongoing)

### Testing (Continuous)
- [ ] **T.1** 🔄 Unit test coverage >80% (ongoing)
- [ ] **T.2** 🔄 Integration tests (weekly)
- [ ] **T.3** 🔄 End-to-end tests (phase completions)
- [ ] **T.4** 🔄 Performance benchmarking (monthly)

### Documentation (Continuous)
- [ ] **D.1** 🔄 Module docstrings (ongoing)
- [ ] **D.2** 🔄 Function docstrings (ongoing)
- [ ] **D.3** 🔄 Architecture documentation (ongoing)
- [ ] **D.4** 🔄 API documentation (ongoing)

### Validation (Continuous)
- [ ] **V.1** 🔄 Domain expert review (weekly)
- [ ] **V.2** 🔄 Data quality checks (ongoing)
- [ ] **V.3** 🔄 Output validation (ongoing)
- [ ] **V.4** 🔄 Performance monitoring (ongoing)

---

## Statistics & Metrics

### Project Progress
- **Total Tasks:** ~210
- **Completed:** ~163 (Weeks 1-11 + APSA format)
- **In Progress:** Week 12 starting
- **Not Started:** ~47 (Weeks 12-16)
- **Completion Rate:** ~78%

### By Phase
| Phase | Tasks | Completed | % Complete |
|-------|-------|-----------|------------|
| Phase 1 (Weeks 1-2) | ~35 | ~35 | 100% |
| Phase 2 (Weeks 3-5) | ~40 | ~40 | 100% |
| Phase 3 (Weeks 6-8) | ~35 | ~35 | 100% |
| Phase 4 (Weeks 9-11) | ~42 | ~42 | 100% |
| Phase 5 (Weeks 12-14) | ~30 | 0 | Starting |
| Phase 6 (Weeks 15-16) | ~25 | 0 | 0% |
| **Total** | **~207** | **~160** | **~77%** |

---

## Updated: June 25, 2026
Next review: July 2, 2026 (end of Week 12 — PDF Ingestion Module)
