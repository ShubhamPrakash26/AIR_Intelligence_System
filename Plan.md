# AIR Clinical Incident Intelligence Engine - Development Plan

**Version:** 1.0.0  
**Last Updated:** May 21, 2026  
**Project Duration:** 16 weeks  
**Team Size:** 1 (with domain expert review)

---

## Project Timeline Overview

```
Phase 1: Data Foundation (Weeks 1-2)
Phase 2: Core Intelligence (Weeks 3-5)
Phase 3: Retrieval & Discovery (Weeks 6-8)
Phase 4: Insight Generation (Weeks 9-11)
Phase 5: PDF & Advanced (Weeks 12-14)
Phase 6: Production Readiness (Weeks 15-16)
```

---

## Phase 1: Data Foundation (Weeks 1-2)

### Week 1: Project Initialization & Excel Parsing

**Status Update (May 21, 2026):** Week 1 goals and deliverables are complete. Parser ingestion has been validated against `data/input/Log.xlsx`, and API integration coverage now includes `/incidents/ingest/excel`.

**Goals:**
- [x] Set up complete project structure
- [x] Initialize Poetry project with dependencies
- [x] Implement Excel parsing module
- [x] Create comprehensive data models

**Deliverables:**
1. Complete directory structure created
2. `pyproject.toml` with all dependencies
3. `src/ingestion/excel_parser.py` - functional parser
4. `src/models/incident.py` - Incident data model
5. Unit tests for parsing module
6. Documentation: Getting Started guide

**Dependencies to Install:**
- pandas, openpyxl (Excel)
- pydantic (Validation)
- python-dotenv (Config)
- pytest, pytest-cov (Testing)

**Acceptance Criteria:**
- Parse sample Excel file successfully
- Extract all required columns
- Handle missing values gracefully
- >80% test coverage
- Type hints on all functions

---

### Week 2: Normalization Engine & Validation

**Status Update (May 21, 2026):** Week 2 deliverables are complete. Normalization, validation, AI analysis modeling, documentation, and test coverage have been implemented and verified with the full test suite.

**Goals:**
- [x] Build normalization engine
- [x] Create schema validators
- [x] Implement error handling
- [x] Write comprehensive tests

**Deliverables:**
1. `src/normalization/engine.py` - Normalization logic implemented
2. `src/normalization/enums.py` - Standard enums defined
3. `src/normalization/mappers.py` - Value mapping implemented
4. `src/ingestion/validators.py` - Schema validation implemented
5. `src/models/analysis.py` - Analysis data model implemented
6. Integration tests for parsing + normalization pipeline completed
7. Documentation: Data Model Reference completed

**Acceptance Criteria:**
- All enum values standardized (Yes/Y/TRUE → true) - complete
- Date formats consistent - complete
- Missing values handled per specification - complete
- No data loss in transformation - complete
- Error messages informative - complete
- >85% test coverage - complete

**Testing Strategy:**
- Unit test each normalization function
- Integration test full pipeline
- Test edge cases (empty values, mixed types, invalid enums)
- Validate output against Pydantic models

---

## Phase 2: Core Intelligence (Weeks 3-5)

### Week 3: Incident Understanding Agent

**Goals:**
- [x] Design incident understanding system
- [x] Implement clinical reasoning logic
- [x] Create classification taxonomy
- [x] Build severity analyzer

**Deliverables:**
1. `src/incident/understanding_agent.py` - Core agent
2. `src/incident/classifiers.py` - Multi-label classification
3. `src/incident/severity_analyzer.py` - Severity engine
4. `src/models/analysis.py` - Extended with AI fields
5. Prompt engineering for LLM integration
6. Documentation: Incident Analysis Guide

**Key Decisions:**
- Use LangGraph for orchestration? (Yes, decided)
- Which LLM for initial MVP? (Claude Opus 4.7)
- Prompt engineering approach? (Few-shot examples + system prompt)

**Acceptance Criteria:**
- Clinical reasoning produces coherent outputs
- Classification aligns with multi-label taxonomy
- Severity scoring consistent (High + Cardiac Arrest = valid)
- Confidence scores meaningful
- Domain expert review: >80% agreement on sample incidents

**Testing Strategy:**
- Unit tests with mock LLM responses
- Integration tests with real LLM (cost-optimized)
- Validation against known incident types
- Severity consistency checks

**Status Update (May 22, 2026):** Week 3 goals and deliverables implemented and unit/integration tests added. Domain expert review script is present (`scripts/domain_review.py`) and domain agreement is pending (3.4.5).

---

### Week 4: Validation Layer & Root Cause Analysis

**Status Update (May 22, 2026):** Week 4 is now effectively complete. A deterministic validation agent, retry/reporting support, output constraints, and root-cause analysis scaffolding are in place, and the parse-to-analysis pipeline is covered by integration tests.

**Goals:**
- [x] Implement validation agent
- [x] Build contradiction detection
- [x] Create root cause analysis engine
- [x] Establish confidence thresholds

**Deliverables:**
1. `src/validation/validator_agent.py` - Validation logic
2. `src/validation/schemas.py` - JSON schemas
3. `src/incident/root_cause_analyzer.py` - RCA engine
4. Validation rules and thresholds
5. Retry logic for failed validations
6. Documentation: Validation Framework

**Critical Validation Rules:**
```
- Contradiction detection: severity="Low" + outcome="Cardiac arrest" = REJECT
- Null checking: incident_type REQUIRED
- Confidence threshold: <0.7 = NEEDS_REVIEW
- Missing learning: If severity="High", key_learning REQUIRED
```

**Acceptance Criteria:**
- Zero hallucinations in validation tests
- Detects contradictions correctly
- Confidence scores guide review priority
- Rejects invalid outputs consistently
- Clear feedback on rejection reasons

---

### Week 5: Embedding Generation & Vector Integration

**Goals:**
- [ ] Integrate embedding model (BGE-M3)
- [ ] Generate vectors for all incidents
- [ ] Set up Qdrant vector store
- [ ] Implement metadata extraction

**Deliverables:**
1. `src/embeddings/engine.py` - Embedding generation
2. `src/embeddings/models.py` - Model wrapper
3. `src/vector_store/qdrant_handler.py` - Qdrant integration
4. `src/vector_store/metadata.py` - Metadata handling
5. Vector generation pipeline
6. Qdrant collection setup and indexing
7. Documentation: Embedding & Vector Store Guide

**Technical Decisions:**
- Embedding model: BGE-M3 (open-source, multilingual)
- Vector dimension: 768 (BGE-M3 standard)
- Chunk size: Full incident narrative (not chunked initially)
- Metadata fields: incident_type, severity, surgery_type, month, year

**Acceptance Criteria:**
- Embedding generation: <500ms per incident
- Vector similarity makes clinical sense
- All metadata properly indexed
- Qdrant queries return relevant results
- Scalable to 10k+ incidents

**Integration Testing:**
- End-to-end pipeline: Parse → Normalize → Analyze → Embed → Store
- Query validation: Similar incidents retrieved correctly

---

## Phase 3: Retrieval & Discovery (Weeks 6-8)

### Week 6: Similarity Search & Retrieval

**Goals:**
- [ ] Implement similarity search engine
- [ ] Add metadata filtering
- [ ] Build reranking system
- [ ] Create retrieval interface

**Deliverables:**
1. `src/retrieval/similarity_search.py` - Core search
2. `src/retrieval/rag.py` - RAG retrieval logic
3. Reranker integration (bge-reranker-large)
4. Metadata filtering system
5. Top-K selection logic
6. Query expansion (optional enhancement)
7. Documentation: Retrieval System Guide

**Search Dimensions:**
- Root cause similarity: "Labeling failures" finds similar medication errors
- Context similarity: "Induction phase" finds incidents at same timing
- Equipment similarity: "Insufflator" finds all insufflator-related incidents
- Outcome similarity: Clusters by harm severity

**Acceptance Criteria:**
- Similarity search latency: <1s for top-5
- Reranking improves relevance significantly
- Metadata filtering reduces false positives
- Clinician validation: >80% retrieved incidents are relevant
- Top-1 retrieval accuracy: >75%

---

### Week 7: Theme Clustering

**Goals:**
- [ ] Implement clustering algorithm (HDBSCAN)
- [ ] Build theme extraction
- [ ] Create pattern summarization
- [ ] Develop clustering visualization

**Deliverables:**
1. `src/retrieval/clustering.py` - Clustering engine
2. Theme naming and description generation
3. Pattern extraction from clusters
4. UMAP visualization
5. Cluster quality metrics
6. Documentation: Theme Clustering Guide

**Clustering Pipeline:**
```
All incident embeddings
  ↓
Dimensionality reduction (UMAP)
  ↓
HDBSCAN clustering
  ↓
Theme naming (LLM-assisted)
  ↓
Pattern extraction
  ↓
Recommendation generation
```

**Acceptance Criteria:**
- Clusters are clinically meaningful
- >5 distinct themes identified in sample data
- Pattern extraction is accurate
- Theme naming is concise and clear
- Silhouette score >0.4 (for quality clusters)

---

### Week 8: RAG Integration

**Goals:**
- [ ] Complete RAG pipeline
- [ ] Integrate all retrieval components
- [ ] Add context grounding
- [ ] Implement evidence tracking

**Deliverables:**
1. `src/retrieval/rag.py` - Complete RAG system
2. Context grounding framework
3. Evidence tracking and attribution
4. Query preprocessing
5. Result aggregation
6. Integration tests for RAG pipeline
7. Documentation: RAG Architecture

**RAG Quality Metrics:**
- Evidence relevance: >85% retrieved documents are relevant
- Grounding effectiveness: <5% claims lack supporting evidence
- Latency: <2s for full RAG retrieval
- Hallucination reduction: Measured via validation

**Acceptance Criteria:**
- Retrieved context improves insight quality
- Evidence clearly attributed to sources
- No unsourced claims in RAG-generated outputs
- System handles queries with no relevant results gracefully

---

## Phase 4: Insight Generation (Weeks 9-11)

### Week 9: Insight Generation Agent

**Goals:**
- [ ] Design insight generation system
- [ ] Implement contextual analysis
- [ ] Build pattern connection logic
- [ ] Create safety recommendations

**Deliverables:**
1. `src/insights/generator.py` - Core generator
2. Contextual analysis framework
3. Pattern connection logic
4. Recommendation engine
5. LLM prompts for insight generation
6. Documentation: Insight Generation Guide

**Insight Quality Requirements:**
- AVOID: "Communication is important"
- TARGET: "Repeated neuraxial drug substitution incidents demonstrate persistent failures in syringe labeling and independent verification workflows"

**Key Prompting Strategies:**
- Few-shot examples of good/bad insights
- System prompt emphasizing systemic analysis
- Context injection: relevant retrieved incidents
- Grounding constraint: Must cite evidence

**Acceptance Criteria:**
- All insights reference relevant incidents
- >90% insights are specific (not generic)
- Domain expert review: >4/5 quality rating
- Actionability: >80% suggest concrete improvements

---

### Week 10: Editorial Intelligence Layer

**Goals:**
- [ ] Implement APSA-style narrative generation
- [ ] Build editorial commentary system
- [ ] Create thematic analysis
- [ ] Ensure tone and quality

**Deliverables:**
1. `src/insights/editorial.py` - Editorial engine
2. Tone and style guidelines
3. APSA newsletter examples for grounding
4. Narrative templates
5. Quality assurance framework
6. Documentation: Editorial Guidelines

**Tone Requirements:**
- Reflective and clinically serious
- Educational and non-punitive
- Evidence-based
- Actionable
- Professional and polished

**Editorial Workflow:**
```
Raw insights
  ↓
Theme grouping
  ↓
Narrative generation
  ↓
Tone adjustment
  ↓
Evidence validation
  ↓
Editorial review
```

**Acceptance Criteria:**
- Outputs match APSA quality standards
- >4/5 editorial review score
- No grammatical errors
- Consistent tone throughout
- Appropriate length (not too verbose)

---

### Week 11: Output Formatting & Integration

**Goals:**
- [ ] Create output formatters
- [ ] Build JSON/text export
- [ ] Implement quality assurance
- [ ] Complete end-to-end integration

**Deliverables:**
1. `src/insights/formatters.py` - Output formatting
2. JSON schema for outputs
3. Markdown/text export
4. Excel report generation
5. End-to-end pipeline integration
6. Complete documentation: Output Formats

**Output Formats:**
- Structured JSON (for downstream processing)
- Markdown (for human reading)
- Excel (for APSA newsletter integration)

**Acceptance Criteria:**
- All output formats are valid
- Data integrity maintained in transformations
- End-to-end pipeline functional
- >90% of incidents processed successfully
- Error handling for edge cases

---

## Phase 5: PDF & Advanced Features (Weeks 12-14)

### Week 12: PDF Ingestion Module

**Goals:**
- [ ] Implement PDF parsing
- [ ] Add OCR support
- [ ] Build layout analysis
- [ ] Create metadata extraction

**Deliverables:**
1. `src/ingestion/pdf_parser.py` - PDF parsing
2. LlamaParse integration
3. Tesseract OCR integration
4. Layout analysis
5. Metadata extraction
6. PDF validation
7. Documentation: PDF Ingestion Guide

**Supported PDF Types:**
- AIR incident reports
- APSA newsletters
- Clinical guidelines
- Literature PDFs
- Hospital incident reports

**Acceptance Criteria:**
- Successfully parse various PDF formats
- OCR accuracy >95% for printed text
- Metadata correctly extracted
- Handling of images, tables, figures
- No loss of critical information

---

### Week 13: Multi-Document RAG

**Goals:**
- [ ] Enhance RAG for multiple documents
- [ ] Implement document ranking
- [ ] Build context aggregation
- [ ] Create literature integration

**Deliverables:**
1. Enhanced RAG system for multi-document retrieval
2. Document-level ranking
3. Cross-document context aggregation
4. Literature grounding system
5. Multi-document integration tests
6. Documentation: Multi-Document RAG

**Multi-Document Scenarios:**
- Single incident with multiple related documents
- Literature-grounded recommendations
- Cross-incident pattern identification
- Historical incident retrieval

**Acceptance Criteria:**
- Relevant documents retrieved across types
- Document ranking prioritizes appropriate sources
- No redundant or conflicting information
- Context properly aggregated

---

### Week 14: Advanced Clustering & Optimization

**Goals:**
- [ ] Optimize clustering algorithm
- [ ] Implement hierarchical clustering
- [ ] Build clustering visualization
- [ ] Create advanced analytics

**Deliverables:**
1. Optimized HDBSCAN implementation
2. Hierarchical clustering
3. Advanced visualization (UMAP, t-SNE)
4. Clustering analytics dashboard (local)
5. Performance optimization
6. Documentation: Advanced Clustering

**Advanced Features:**
- Hierarchical theme exploration
- Temporal trend analysis
- Subgroup clustering
- Anomaly detection

**Acceptance Criteria:**
- Clustering scales to 10k+ incidents
- Visualization reveals clinical patterns
- Performance metrics tracked
- Reproducible results (seeded)

---

## Phase 6: Production Readiness (Weeks 15-16)

### Week 15: API Development & Testing

**Goals:**
- [ ] Build FastAPI application
- [ ] Implement all endpoints
- [ ] Write comprehensive tests
- [ ] Set up Docker containers

**Deliverables:**
1. FastAPI application (`main.py`)
2. API endpoints for all major functions
3. Request/response models
4. Error handling and logging
5. Docker setup (Dockerfile, docker-compose.yml)
6. Unit and integration test suite (>90% coverage)
7. Documentation: API Reference

**Key Endpoints:**
- `POST /incidents/parse` - Parse and ingest incidents
- `POST /incidents/analyze` - Analyze incident
- `GET /incidents/{id}` - Retrieve incident
- `GET /search/similar/{id}` - Similarity search
- `GET /themes` - Get all themes
- `POST /insights/generate` - Generate insights
- `GET /health` - Health check

**Acceptance Criteria:**
- All endpoints functional
- Error handling comprehensive
- Response times acceptable
- >90% test coverage
- Docker container builds successfully
- Security best practices implemented

---

### Week 16: Documentation & Deployment Readiness

**Goals:**
- [ ] Complete all documentation
- [ ] Deploy to staging
- [ ] Performance testing
- [ ] Handoff preparation

**Deliverables:**
1. Complete API documentation (OpenAPI/Swagger)
2. Development guide for future maintainers
3. Deployment guide
4. Troubleshooting guide
5. Performance benchmarks
6. Staging deployment verified
7. README with quick start guide

**Documentation Checklist:**
- [ ] Architecture decisions documented
- [ ] API endpoints documented with examples
- [ ] Configuration guide
- [ ] Deployment procedures
- [ ] Common issues and solutions
- [ ] Contributing guidelines

**Performance Targets:**
- Incident parsing: <1s per incident
- Incident analysis: <5s per incident
- Similarity search: <1s for top-5
- Insight generation: <10s
- Batch processing: 100 incidents in <5 minutes

**Acceptance Criteria:**
- System meets all specified performance targets
- Documentation is clear and complete
- Staging deployment successful
- Ready for production deployment

---

## Cross-Phase Activities

### Testing Strategy (Continuous)
- Unit tests: Written with each feature
- Integration tests: End-of-phase
- End-to-end tests: Phase completions
- Domain expert validation: Weekly
- Performance testing: Monthly

### Code Quality (Continuous)
- Type hints on all code
- Docstrings (Google style)
- Code review before merge
- Linting with Ruff
- Formatting with Black
- Type checking with mypy

### Documentation (Continuous)
- Inline code comments
- Module docstrings
- API documentation
- Architecture diagrams
- Decision records (ADRs)

### Monitoring & Logging (Built-in)
- Structured logging (JSON format)
- Error tracking
- Performance metrics
- Data quality checks

---

## Risk Management

### High Risks

| Risk | Mitigation |
|------|-----------|
| LLM hallucinations | Validation layer, confidence thresholds, RAG grounding |
| Data quality issues | Schema validation, comprehensive testing |
| Clustering instability | Seed setting, validation of results |
| Performance degradation at scale | Early performance testing, optimization |

### Medium Risks

| Risk | Mitigation |
|------|-----------|
| PDF parsing accuracy | Tesseract tuning, manual QA |
| Embedding quality | Model validation, similarity testing |
| Theme interpretation | Domain expert review |

### Monitoring

- Weekly domain expert review
- Bi-weekly performance metrics
- Monthly data quality audit
- Continuous error rate monitoring

---

## Success Criteria by Phase

### Phase 1: Data Foundation ✓
- [x] All parsing and normalization complete
- [x] Test coverage >80%
- [x] Sample data processes cleanly

### Phase 2: Core Intelligence ✓
- [x] Incident understanding functional
- [x] Validation catches contradictions
- [x] Domain expert agreement >80%
- [x] Vectors generated and stored

### Phase 3: Retrieval & Discovery ✓
- [x] Similarity search effective
- [x] Themes are clinically meaningful
- [x] RAG integration complete

### Phase 4: Insight Generation ✓
- [x] Insights are specific and actionable
- [x] Editorial quality >4/5
- [x] All insights grounded in evidence

### Phase 5: PDF & Advanced ✓
- [x] PDF parsing functional
- [x] Multi-document RAG works
- [x] Advanced clustering operational

### Phase 6: Production Readiness ✓
- [x] API fully functional
- [x] >90% test coverage
- [x] Complete documentation
- [x] Performance targets met

---

## Resource Requirements

### Tools & Services
- Python 3.11+ environment
- Qdrant (self-hosted or Qdrant Cloud)
- Anthropic API (Claude Sonnet) or local LLM
- Git + GitHub
- Docker
- Optional: Cloud infrastructure (AWS/GCP/Azure) for deployment

### Knowledge Required
- Python programming (advanced)
- Clinical/medical domain knowledge (reference materials provided)
- Machine learning fundamentals
- Data structures and algorithms
- API design
- Database concepts

### Estimated Effort
- Total: ~16 weeks full-time
- Can be distributed: 2-3 weeks part-time per phase
- Domain expert review: 2-3 hours per week

---

## Next Steps

1. **Immediately:** Proceed to Phase 1, Week 1
2. **This week:** Set up project structure, install dependencies, begin Excel parsing
3. **Next week:** Complete normalization engine, begin testing
4. **Ongoing:** Weekly domain expert review sessions

---

**Plan Last Updated:** May 20, 2026  
**Next Review:** May 27, 2026 (end of Week 1)
