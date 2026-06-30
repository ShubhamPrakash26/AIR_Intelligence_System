# AIR Clinical Incident Intelligence Engine

**Version:** 1.0.0  
**Status:** Phase 5 Complete — Phase 6: Production Readiness (Weeks 15-16) Next

## Overview

The AIR Clinical Incident Intelligence Engine is a standalone AI-powered clinical safety intelligence platform designed to:

- **Ingest** AIR (Anaesthesia Incident Registry) logs from Excel, CSV, and PDF formats
- **Understand** perioperative incidents through clinical reasoning
- **Identify** recurring patient safety risks using semantic analysis
- **Detect** systemic failures through root cause analysis
- **Retrieve** related historical incidents and literature via RAG
- **Generate** grounded clinical insights using an Agentic architecture
- **Create** APSA-style editorial intelligence

## Core Philosophy

**This system is NOT:** Excel → GPT Prompt → Summary

**This system IS:** Clinical Incident Intelligence Pipeline + Semantic Retrieval System + Agentic Safety Analysis Engine + Editorial Intelligence Platform

## Quick Start

### Prerequisites

- Python 3.11+
- Poetry (Python dependency manager)
- Git
- Qdrant (vector database)
- Anthropic API Key (for Claude access)

### Installation

1. **Clone the repository** (if applicable)
   ```bash
   git clone <repository>
   cd AIR_Intelligence_System
   ```

2. **Install dependencies using Poetry**
   ```bash
   poetry install
   ```

3. **Activate the Poetry environment**
   ```bash
   poetry shell
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

5. **Start Qdrant** (if not already running)
   ```bash
   docker run -p 6333:6333 qdrant/qdrant
   ```

### Running the System

#### Development Mode
```bash
poetry run python main.py --dev
```

#### API Server
```bash
poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### Process Sample Data
```bash
poetry run python -m src.ingestion.excel_parser data/input/sample.xlsx
```

## Project Structure

```
AIR_Intelligence_System/
├── src/
│   ├── ingestion/           # Excel/PDF parsing
│   ├── normalization/       # Data standardization
│   ├── incident/            # Incident analysis agents
│   ├── validation/          # Output validation
│   ├── embeddings/          # Vector generation
│   ├── vector_store/        # Qdrant integration
│   ├── retrieval/           # Search & clustering
│   ├── insights/            # Insight generation
│   ├── agents/              # LangGraph orchestration
│   ├── models/              # Data models
│   └── utils/               # Utilities & config
├── tests/
│   ├── unit/                # Unit tests
│   ├── integration/         # Integration tests
│   └── fixtures/            # Test data
├── data/
│   ├── input/               # Raw input files
│   ├── processed/           # Processed incidents
│   └── embeddings/          # Generated vectors
├── docs/                    # Documentation
├── pyproject.toml           # Poetry dependencies
├── README.md                # This file
├── Plan.md                  # Development plan
├── Tasks.md                 # Task tracking
└── project_overview.md      # Complete project documentation
```

## Development Roadmap

### Phase 1: Data Foundation (Weeks 1-2) ✅ Complete
- [x] Project initialization
- [x] Excel parsing module
- [x] Data normalization engine
- [x] Schema validation

### Phase 2: Core Intelligence (Weeks 3-5) ✅ Complete
- [x] Incident understanding agent (Claude LLM)
- [x] Validation layer
- [x] Embedding generation (BGE-M3)
- [x] Vector store integration (Qdrant)

### Phase 3: Retrieval & Discovery (Weeks 6-8) ✅ Complete
- [x] Similarity search + cross-encoder reranking
- [x] Theme clustering (HDBSCAN + UMAP)
- [x] RAG integration (standard + grounded)

### Phase 4: Insight Generation (Weeks 9-11) ✅ Complete
- [x] Insight generation agent (APSA-style)
- [x] Editorial intelligence layer (ToneValidator, NarrativeBuilder)
- [x] Output formatting (Markdown, Excel, JSON) + pipeline router

### Phase 5: PDF & Advanced (Weeks 12-14) ✅ Complete
- [x] PDF ingestion (`fix_doubled_chars` normalizer)
- [x] Multi-source RAG (incidents + literature, single Qdrant collection)
- [x] Anomaly detection + temporal pattern analysis

### Phase 6: Production Readiness (Weeks 15-16) 🔄 In Progress
- [ ] Docker containerisation
- [ ] API authentication
- [ ] Load testing & benchmarking
- [ ] Complete documentation & deployment guide

## Key Features

### Data Ingestion
- ✅ Excel (.xlsx, .xls, .csv) support
- ✅ PDF document support (AIR Log form-fill PDFs, `fix_doubled_chars` normalizer)
- ✅ Clinical literature batch ingest (JSON)
- ✅ Batch processing

### AI Pipeline
- ✅ Clinical incident understanding (Claude LLM, LangChain)
- ✅ Severity analysis
- ✅ Root cause analysis
- ✅ Multi-label classification
- ✅ Confidence scoring + validation layer

### Vector Intelligence
- ✅ Semantic embedding (BGE-M3, 1024-dim)
- ✅ Qdrant vector store (in-memory + remote)
- ✅ Similarity search + cross-encoder reranking
- ✅ Metadata filtering (severity, surgery type, year, source type)
- ✅ Multi-source retrieval (incidents + literature, single collection)

### Retrieval & Learning
- ✅ RAG-grounded retrieval (standard + grounded with evidence tracking)
- ✅ Theme clustering (HDBSCAN + UMAP, auto_params mode)
- ✅ Anomaly detection (HDBSCAN noise-point labelling)
- ✅ Temporal pattern analysis (trend direction, acceleration, severity trend)

### Insight Generation
- ✅ Clinical reasoning (InsightGenerator, APSA system prompt)
- ✅ Safety recommendations
- ✅ Editorial intelligence (ToneValidator, 28 forbidden phrases, NarrativeBuilder)
- ✅ APSA-style Markdown / Excel / JSON output

## Testing

### Run All Tests
```bash
poetry run pytest
```

### Run with Coverage
```bash
poetry run pytest --cov=src --cov-report=html
```

### Run Specific Test Suite
```bash
poetry run pytest tests/unit/          # Unit tests only
poetry run pytest tests/integration/   # Integration tests only
poetry run pytest -k test_parser       # Specific test
```

## Code Quality

### Format Code
```bash
poetry run black src/ tests/
```

### Lint Code
```bash
poetry run ruff check src/ tests/
```

### Type Checking
```bash
poetry run mypy src/
```

## Documentation

- **[project_overview.md](project_overview.md)** - Complete architecture and design documentation
- **[Plan.md](Plan.md)** - Detailed development plan and timeline
- **[Tasks.md](Tasks.md)** - Task tracking and progress
- **API Documentation** - Auto-generated at `/docs` when API is running

## Configuration

All configuration is managed via environment variables. See [.env.example](.env.example) for all available settings.

Key settings:
- `ANTHROPIC_API_KEY` - Your Anthropic API key for Claude
- `QDRANT_URL` - Vector database connection URL
- `LLM_MODEL` - Language model to use (default: claude-sonnet-4-6)
- `CONFIDENCE_THRESHOLD` - Minimum confidence for validation (default: 0.7)

## Contributing

1. Create a feature branch: `git checkout -b feature/name`
2. Make your changes following code quality standards
3. Write tests for new functionality
4. Submit a pull request

## Code Standards

- **Language:** Python 3.11+
- **Type Hints:** Required on all functions
- **Docstrings:** Google style for all modules and functions
- **Testing:** >80% coverage required
- **Linting:** Ruff with default settings
- **Formatting:** Black with 100 character line length

## Performance Targets

- Incident parsing: <1s per incident
- Incident analysis: <5s per incident
- Similarity search: <1s for top-5
- Insight generation: <10s
- Batch processing: 100 incidents in <5 minutes

## License

MIT License - See LICENSE file for details

## Contact & Support

For issues, questions, or contributions, please refer to the project documentation and development guidelines.

---

**Last Updated:** June 30, 2026  
**Current Phase:** Phase 5 Complete — Phase 6: Production Readiness (Weeks 15-16)  
**Next Milestone:** Docker containerisation, API auth, load testing, deployment guide
