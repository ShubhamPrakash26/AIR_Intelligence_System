# AIR Clinical Incident Intelligence Engine - Project Overview

**Version:** 1.0.0  
**Last Updated:** May 22, 2026  
**Status:** Phase 2 - Core Intelligence (Week 4 Complete)  

---

## 1. Project Summary

### Name
**AIR Clinical Incident Intelligence Engine**

### Purpose
A standalone AI-powered clinical safety intelligence platform designed to:
- Ingest AIR (Anaesthesia Incident Registry) logs from multiple formats
- Understand perioperative incidents through clinical reasoning
- Identify recurring patient safety risks using semantic analysis
- Detect systemic failures through root cause analysis
- Retrieve related historical incidents and literature via RAG
- Generate grounded clinical insights using an Agentic architecture

### Core Principle
**This system is NOT:** Excel → GPT Prompt → Summary  
**This system IS:** Clinical Incident Intelligence Pipeline + Semantic Retrieval System + Agentic Safety Analysis Engine + Editorial Intelligence Platform

---

## 2. Primary Objectives

| Objective | Description | Priority |
|-----------|-------------|----------|
| Parse AIR logs | Handle structured + semi-structured data (Excel/CSV/PDF) | P0 |
| Understand incidents | Clinical + system-level reasoning | P0 |
| Extract root causes | Detect systemic failures (not just events) | P0 |
| Generate embeddings | Semantic understanding for retrieval | P0 |
| Detect recurring themes | Cross-case pattern discovery | P1 |
| Retrieve similar cases | Historical memory and context | P1 |
| Ground outputs using RAG | Reduce hallucinations with evidence | P1 |
| Generate actionable insights | Editorial-quality learnings | P1 |
| Support scalability | Foundation for national safety intelligence | P2 |

---

## 3. Input Sources & Formats

### 3.1 Excel Logs
- **Supported Formats:** `.xlsx`, `.xls`, `.csv`
- **Expected Columns:**
  - Patient Information: Age, Sex, Weight, Height, BMI, ASA Grade
  - Surgical Context: Type, Branch, Procedure
  - Incident Data: Description, Anesthesia Technique, Monitoring
  - Clinical Tags: Airway, Respiratory, Cardiac, Equipment, Positioning
  - Medication Errors: Type, Cause
  - Outcomes: Morbidity, Patient Safety, Personnel Safety
  - Patient Outcome Category: Category A-E rating

### 3.2 PDF Documents
- **Supported Types:**
  - AIR reports (historical retrieval)
  - APSA newsletters (tone grounding)
  - Clinical guidelines (evidence grounding)
  - Literature PDFs (RAG augmentation)
  - Hospital incident reports

---

## 4. End-to-End Architecture

```
┌──────────────────────────────────────────────────┐
│          DATA INGESTION LAYER                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────┐  │
│  │   Excel     │  │     PDF     │  │  JSON   │  │
│  │  Files      │  │  Reports    │  │  Logs   │  │
│  └──────┬──────┘  └──────┬──────┘  └────┬────┘  │
└─────────┼─────────────────┼──────────────┼────────┘
          │                 │              │
          └────────────┬────┴──────────────┘
                       │
                       ▼
          ┌────────────────────────────────┐
          │   PARSING & VALIDATION         │
          │   - Schema validation          │
          │   - OCR for PDFs               │
          │   - Field extraction           │
          └────────────┬───────────────────┘
                       │
                       ▼
          ┌────────────────────────────────┐
          │  NORMALIZATION ENGINE          │
          │  - Enum standardization        │
          │  - Date formatting             │
          │  - Boolean normalization       │
          │  - Missing value handling      │
          └────────────┬───────────────────┘
                       │
                       ▼
          ┌────────────────────────────────┐
          │ INCIDENT UNDERSTANDING AGENT   │
          │  - Clinical reasoning          │
          │  - Incident classification     │
          │  - Severity analysis           │
          │  - Root cause extraction       │
          │  - Contributing factors        │
          │  - Learning generation         │
          └────────────┬───────────────────┘
                       │
                       ▼
          ┌────────────────────────────────┐
          │  VALIDATION AGENT              │
          │  - JSON schema validation      │
          │  - Taxonomy checking           │
          │  - Contradiction detection     │
          │  - Confidence scoring          │
          └────────────┬───────────────────┘
                       │
                       ▼
          ┌────────────────────────────────┐
          │  EMBEDDING GENERATION          │
          │  - Vector generation           │
          │  - Metadata extraction         │
          └────────────┬───────────────────┘
                       │
                       ▼
          ┌────────────────────────────────┐
          │  VECTOR STORE (Qdrant)         │
          │  - Semantic indexing           │
          │  - Metadata storage            │
          └────────────┬───────────────────┘
                       │
       ┌───────────────┼───────────────┐
       │               │               │
       ▼               ▼               ▼
  ┌─────────┐  ┌────────────┐  ┌────────────┐
  │Similarity│  │   Theme    │  │  Metadata  │
  │ Search  │  │ Clustering │  │   Search   │
  └────┬────┘  └──────┬─────┘  └────┬───────┘
       │               │             │
       └───────────────┼─────────────┘
                       │
                       ▼
          ┌────────────────────────────────┐
          │  RAG RETRIEVAL LAYER           │
          │  - Semantic search             │
          │  - Metadata filtering          │
          │  - Reranking (bge-reranker)    │
          │  - Top-K selection             │
          └────────────┬───────────────────┘
                       │
                       ▼
          ┌────────────────────────────────┐
          │  INSIGHT GENERATION AGENT      │
          │  - Contextual analysis         │
          │  - Pattern connection          │
          │  - Safety recommendations      │
          │  - Evidence grounding          │
          └────────────┬───────────────────┘
                       │
                       ▼
          ┌────────────────────────────────┐
          │  EDITORIAL INTELLIGENCE        │
          │  - APSA-style narratives       │
          │  - Thematic commentary         │
          │  - Reflective analysis         │
          │  - Safety observations         │
          └────────────┬───────────────────┘
                       │
                       ▼
          ┌────────────────────────────────┐
          │  OUTPUT GENERATION             │
          │  - Structured insights         │
          │  - JSON outputs                │
          │  - Editorial summaries         │
          └────────────────────────────────┘
```

---

## 5. AI Pipeline Stages

### Complete Processing Flow

1. **File Ingestion** - Load and parse input files
2. **Schema Validation** - Verify structure and required fields
3. **Data Cleaning** - Handle anomalies and inconsistencies
4. **Normalization** - Standardize values and enums
5. **Clinical Entity Extraction** - Identify key medical entities
6. **Incident Understanding** - Comprehensive clinical analysis
7. **Severity Analysis** - Determine clinical seriousness
8. **Root Cause Analysis** - Extract systemic failures
9. **Learning Generation** - Generate preventive insights
10. **Validation** - Verify output quality and consistency
11. **Embedding Generation** - Create semantic vectors
12. **Vector Storage** - Index in Qdrant
13. **Similarity Retrieval** - Find related incidents
14. **Theme Clustering** - Detect patterns
15. **RAG Retrieval** - Ground with context
16. **Insight Generation** - Create actionable intelligence
17. **Editorial Intelligence** - Professional presentation
18. **Structured Output** - Generate final deliverables

---

## 6. Core Components

### 6.1 Excel Ingestion Module
**Responsibilities:**
- Load spreadsheets using pandas
- Validate schema against expected columns
- Detect and handle missing values
- Normalize inconsistent data types
- Convert rows into incident objects
- Preserve narrative context

**Handling Requirements:**
| Problem | Solution |
|---------|----------|
| Missing values | Normalize to null |
| Mixed booleans | Standardize to true/false |
| Inconsistent naming | Apply mapping rules |
| Sparse columns | Use safe defaults |
| Narrative-heavy rows | Preserve full context |

### 6.2 PDF Ingestion Module
**Responsibilities:**
- Extract text via OCR (Tesseract)
- Parse layouts using LlamaParse
- Chunk documents intelligently
- Extract metadata (title, date, type)
- Generate embeddings for content
- Index in vector store

**Recommended Stack:**
- **OCR:** Tesseract
- **PDF Parsing:** LlamaParse
- **Layout Analysis:** Unstructured.io

### 6.3 Normalization Engine
**Responsibilities:**
- Standardize enums (Yes/Y/TRUE → true)
- Normalize boolean values
- Handle missing values consistently
- Standardize date formats
- Map surgical taxonomy
- Validate value ranges

### 6.4 Incident Understanding Agent
**Purpose:** Clinical reasoning + system analysis (NOT summarization)

**Responsibilities:**
- Understand event (clinical interpretation)
- Identify failures (system understanding)
- Classify incident (taxonomy assignment)
- Assess severity (risk grading)
- Extract root causes (safety analysis)
- Generate learnings (preventive insights)

**Input:**
```json
{
  "incident_description": "...",
  "incident_details": "...",
  "surgical_context": "...",
  "outcome": "..."
}
```

**Output:**
```json
{
  "incident_type": ["Medication Error", "Communication Failure"],
  "severity": "High",
  "root_cause": "Absence of functional pre-use verification...",
  "contributing_factors": ["Equipment maintenance gap", "Inadequate escalation workflow"],
  "key_learning": "Multi-disciplinary coordination...",
  "confidence_score": 0.92
}
```

### 6.5 Incident Classification System
**Multi-Label Taxonomy:**
- Equipment Failure
- Medication Error
- Airway Event
- Respiratory Event
- Cardiac Event
- Human Error
- Communication Failure
- Workflow Failure
- Checklist Failure
- Positioning Injury
- Monitoring Failure
- System Failure

### 6.6 Severity Analysis Engine
**Scale:** Low → Moderate → High → Critical

**Inputs:**
- AIR outcome category
- Harm severity
- Narrative cues
- Interventions required

### 6.7 Root Cause Analysis Engine
**Philosophy:** Extract SYSTEMIC failures, not just events

**Contributing Factor Categories:**
- Human Factors
- Communication Gaps
- Training Deficiencies
- Checklist Noncompliance
- Workflow Design
- Equipment Maintenance
- Environmental Conditions
- Monitoring Failures

### 6.8 Validation Layer
**Critical Component:** Without validation, hallucinations increase and themes become unstable

**Validation Types:**
- **JSON Schema:** Pydantic validation
- **Taxonomy:** Controlled vocabulary checking
- **Contradictions:** Validation agent
- **Confidence:** Threshold filtering
- **Missing Outputs:** Reprocessing

**Example Rejection:**
```json
{
  "severity": "Low",
  "outcome": "Cardiac arrest"
}
// REJECTED - Contradiction detected
```

### 6.9 Embedding Engine
**Purpose:** Generate semantic vectors for incidents, root causes, themes, learnings

**Recommended Models:**
- **BGE-M3:** Best open-source option
- **text-embedding-3-large:** Best API option
- **Instructor-XL:** Strong alternative

### 6.10 Vector Store (Qdrant)
**Why Qdrant?**
- Fast semantic search
- Metadata filtering for hybrid retrieval
- Production-ready and scalable
- Excellent APIs for integration

**Stored Metadata:**
```json
{
  "incident_type": "Medication Error",
  "severity": "High",
  "surgery_type": "Emergency",
  "month": "April",
  "year": 2026
}
```

### 6.11 Similarity Search Engine
**Purpose:** Retrieve similar incidents, repeated failures, historical analogues

**Similarity Dimensions:**
- Root cause similarity
- Contextual similarity
- Equipment-specific patterns
- Outcome-based clustering

### 6.12 Theme Clustering Engine
**Purpose:** Detect recurring failures, hidden safety trends, systemic weaknesses

**Algorithm Selection:**
- **MVP:** KMeans
- **Production:** HDBSCAN
- **Visualization:** UMAP

**Output Example:**
```json
{
  "theme": "Medication Safety Failures",
  "incident_count": 14,
  "patterns": ["look-alike ampoules", "missing independent verification"]
}
```

### 6.13 RAG Retrieval System
**Components:**
- Semantic search (primary retrieval)
- Metadata filtering (context refinement)
- Reranking (relevance scoring)
- **Reranker:** bge-reranker-large

### 6.14 Insight Generation Agent
**Philosophy:** Generate grounded, systemic insights (NOT generic commentary)

**Bad Example:** "Communication is important"  
**Good Example:** "Repeated neuraxial drug substitution incidents demonstrate persistent failures in syringe labeling and independent verification workflows"

### 6.15 Editorial Intelligence Layer
**Purpose:** APSA-style narratives, thematic commentary, editorial reflections

**Tone Requirements:**
- Reflective and clinically serious
- Educational and non-punitive
- Editorial-quality language
- Evidence-grounded

---

## 7. Agentic Workflow Architecture

### Orchestration Framework: LangGraph

**Why LangGraph?**
- Handles retries and branching
- Manages validation loops
- Maintains persistent state
- Supports multi-agent coordination

### Agent Processing Graph

```
START
  │
  ▼
┌─────────────────┐
│ File Parser     │ - Load and parse input
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Normalizer      │ - Standardize data
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│ Incident Understanding      │ - Clinical analysis
│ Agent                       │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────┐
│ Validation      │ - Quality check
│ Agent           │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Embedding       │ - Vector generation
│ Generator       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Vector Store    │ - Index storage
│ Handler         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Theme Clustering│ - Pattern detection
│ Agent           │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Retriever       │ - RAG search
│ Agent           │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│ Insight Generator           │ - Generate insights
│ Agent                       │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────┐
│ Editorial       │ - Professional output
│ Agent           │
└────────┬────────┘
         │
         ▼
END
```

---

## 8. Data Models

### Incident Model
```python
class Incident(BaseModel):
    incident_id: str
    patient: dict  # {age, sex, weight, height, bmi, asa_grade}
    surgery: dict  # {type, branch, procedure}
    incident: dict  # {description, narrative, technique, monitoring}
    context: dict  # {time, place, timing, detection_method}
    outcome: dict  # {category, morbidity, harm}
    metadata: dict  # {source_file, upload_date}
```

### AI Analysis Model
```python
class AIAnalysis(BaseModel):
    incident_type: List[str]  # Multi-label classification
    severity: str  # Low/Moderate/High/Critical
    root_cause: str  # Systemic failure description
    contributing_factors: List[str]
    key_learning: str  # Preventive insight
    confidence_score: float  # 0-1
    validation_status: str  # Valid/Invalid/Needs Review
```

### Theme Model
```python
class Theme(BaseModel):
    theme_id: str
    theme_name: str
    incident_count: int
    patterns: List[str]
    severity_distribution: dict
    recommendations: List[str]
```

### Vector Metadata Model
```python
class VectorMetadata(BaseModel):
    incident_id: str
    incident_type: List[str]
    severity: str
    surgery_type: str
    root_cause: str
    month: str
    year: int
    source: str
```

---

## 9. Technology Stack

### Core Technologies

| Layer | Component | Recommendation | Rationale |
|-------|-----------|-----------------|-----------|
| **Language** | Python 3.11+ | Python | Data science ecosystem, AI libraries |
| **API Framework** | FastAPI | FastAPI | Modern, async, auto-docs |
| **Orchestration** | LangGraph | LangGraph | Multi-agent coordination, retries, state |
| **Validation** | Pydantic | Pydantic | Type safety, schema validation |
| **Embeddings** | BGE-M3 | BGE-M3 | Best open-source option |
| **Vector DB** | Qdrant | Qdrant | Production-ready, hybrid search |
| **Reranker** | bge-reranker-large | bge-reranker | Relevance scoring |
| **Clustering** | HDBSCAN | HDBSCAN | Density-based, no K selection |
| **PDF Processing** | LlamaParse | LlamaParse | Layout-aware parsing |
| **OCR** | Tesseract | Tesseract | Open-source, reliable |
| **Excel Processing** | pandas | pandas | Standard library |
| **LLM (Initial)** | GPT-4 | GPT-4 | High reasoning capability |
| **LLM (Future)** | Qwen 2.5 72B | Qwen 2.5 | Open-source alternative |

### Development Tools

- **Version Control:** Git
- **Environment Management:** Poetry (Python dependency management)
- **Code Quality:** Black, Ruff, mypy
- **Testing:** pytest, pytest-asyncio
- **Documentation:** MkDocs
- **Docker:** Containerization for deployment

---

## 10. Development Order (CRITICAL)

**MUST FOLLOW THIS EXACT ORDER:**

### Phase 1: Data Foundation (Weeks 1-2)
1. ✓ Project initialization & structure
2. Excel parsing & schema validation
3. Normalization engine
4. Data models & validation

### Phase 2: Core Intelligence (Weeks 3-5)
5. Incident understanding agent
6. Validation layer
7. Embedding generation
8. Vector store integration

### Phase 3: Retrieval & Discovery (Weeks 6-8)
9. Similarity search engine
10. Theme clustering
11. RAG retrieval system

### Phase 4: Insight Generation (Weeks 9-11)
12. Insight generation agent
13. Editorial intelligence layer
14. Output formatting

### Phase 5: PDF & Advanced (Weeks 12-14)
15. PDF ingestion module
16. Multi-document RAG
17. Advanced clustering

### Phase 6: Production Readiness (Weeks 15-16)
18. API development (FastAPI)
19. Testing & validation
20. Documentation & deployment

**What NOT to Build Initially:**
- ❌ Frontend/Dashboard
- ❌ PDF generation
- ❌ Authentication/Authorization
- ❌ Notification systems

**Until:** The intelligence engine quality is excellent

---

## 11. Project Structure

```
AIR_Intelligence_System/
│
├── .github/
│   └── workflows/          # CI/CD pipelines
│
├── src/
│   ├── __init__.py
│   │
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── excel_parser.py
│   │   ├── pdf_parser.py
│   │   └── validators.py
│   │
│   ├── normalization/
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   ├── mappers.py
│   │   └── enums.py
│   │
│   ├── incident/
│   │   ├── __init__.py
│   │   ├── understanding_agent.py
│   │   ├── classifiers.py
│   │   └── severity_analyzer.py
│   │
│   ├── validation/
│   │   ├── __init__.py
│   │   ├── validator_agent.py
│   │   └── schemas.py
│   │
│   ├── embeddings/
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   └── models.py
│   │
│   ├── vector_store/
│   │   ├── __init__.py
│   │   ├── qdrant_handler.py
│   │   └── metadata.py
│   │
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── similarity_search.py
│   │   ├── clustering.py
│   │   └── rag.py
│   │
│   ├── insights/
│   │   ├── __init__.py
│   │   ├── generator.py
│   │   ├── editorial.py
│   │   └── formatters.py
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── graph.py            # LangGraph orchestration
│   │   └── workflows.py
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── incident.py
│   │   ├── analysis.py
│   │   ├── theme.py
│   │   └── vector.py
│   │
│   └── utils/
│       ├── __init__.py
│       ├── logger.py
│       ├── config.py
│       └── helpers.py
│
├── tests/
│   ├── __init__.py
│   ├── unit/
│   │   ├── test_parsers.py
│   │   ├── test_normalization.py
│   │   ├── test_agents.py
│   │   └── test_models.py
│   ├── integration/
│   │   ├── test_pipeline.py
│   │   └── test_rag.py
│   └── fixtures/
│       ├── sample_excel.py
│       └── sample_incidents.py
│
├── data/
│   ├── input/               # Raw input files
│   │   ├── excel_logs/
│   │   └── pdf_documents/
│   ├── processed/           # Processed incidents
│   └── embeddings/          # Generated vectors
│
├── docs/
│   ├── architecture.md
│   ├── api.md
│   ├── development.md
│   └── deployment.md
│
├── .env.example
├── pyproject.toml           # Poetry dependencies
├── README.md
├── Plan.md                  # Development plan
├── Tasks.md                 # Task tracking
└── project_overview.md      # This file
```

---

## 12. Best Practices

### Code Quality
- Type hints on all functions
- Comprehensive docstrings (Google style)
- Pydantic models for all data structures
- Error handling with custom exceptions
- Logging at appropriate levels

### Testing
- Unit tests for each module (>80% coverage)
- Integration tests for pipelines
- Fixture-based test data
- Parametrized tests for variations

### Documentation
- Inline code comments for complex logic
- Module-level docstrings
- API documentation with examples
- Development guide for contributors

### CI/CD
- GitHub Actions workflows
- Automated testing on push
- Code quality checks
- Build verification

### Version Control
- Semantic versioning (MAJOR.MINOR.PATCH)
- Descriptive commit messages
- Feature branches for development
- Code review before merging

---

## 13. Success Metrics

### Phase 1 Completion
- ✓ Schema validation accuracy: >95%
- ✓ Data normalization: All fields consistent
- ✓ Test coverage: >80%

### Phase 2 Completion
- ✓ Incident understanding: Domain expert review >85% agreement
- ✓ Classification accuracy: >90%
- ✓ Validation: Zero hallucinations in sample set

### Phase 3 Completion
- ✓ Similarity search: Clinician validation >80% relevance
- ✓ Theme clustering: Identified patterns match domain knowledge
- ✓ RAG: Evidence grounding reduces unsupported claims to <5%

### Phase 4 Completion
- ✓ Insight generation: Editorial review quality score >4/5
- ✓ Actionability: >80% insights suggest concrete improvements

---

## 14. Deployment Strategy

### Local Development
- Poetry-managed environment
- Docker for consistent development setup

### Staging
- Docker containers
- Qdrant in-memory or standalone

### Production
- Containerized microservices
- Cloud-hosted Qdrant (Qdrant Cloud)
- FastAPI with Uvicorn
- Horizontal scaling support

---

## 15. Future Enhancements

- Real-time incident streaming
- Predictive safety risk models
- Integration with hospital EMR systems
- Multi-language support
- Mobile companion app
- Automated regulatory reporting

---

## Document Management

**This document is the ultimate source of truth for:**
- Architecture decisions
- Technology choices
- Project structure
- Development roadmap
- Data models
- Success criteria

**Updates required when:**
- Architecture changes
- New components added
- Technology stack changes
- Major design decisions made

**Last verified:** May 20, 2026
