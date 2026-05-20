# AIR Clinical Incident Intelligence Engine - Documentation Index

**Quick Navigation Guide for All Project Documents**

---

## 🎯 Start Here

### For New Team Members
1. **[README.md](README.md)** - Project overview and quick start (5 min read)
2. **[GETTING_STARTED.md](GETTING_STARTED.md)** - Setup instructions (10 min)
3. **[WEEK1_SUMMARY.md](WEEK1_SUMMARY.md)** - What's been completed (10 min)

### For Project Managers
1. **[Plan.md](Plan.md)** - 16-week development roadmap
2. **[Tasks.md](Tasks.md)** - Task tracking with 200+ items
3. **[DEVELOPMENT_STATUS.md](DEVELOPMENT_STATUS.md)** - Current status dashboard

### For Architects & Senior Developers
1. **[project_overview.md](project_overview.md)** - Complete technical architecture
2. **[DEVELOPMENT_STATUS.md](DEVELOPMENT_STATUS.md)** - Component status
3. **[WEEK1_SUMMARY.md](WEEK1_SUMMARY.md)** - Implementation details

---

## 📚 Comprehensive Documentation Map

### Master Documents (SSOT - Single Source of Truth)

**[project_overview.md](project_overview.md)** - 650+ lines
- **Purpose:** Ultimate technical reference for the entire system
- **Contains:** Architecture, data models, technology choices, all components
- **Audience:** Architects, senior developers, decision makers
- **Update Frequency:** When architecture changes
- **Key Sections:**
  - Project summary and philosophy
  - Primary objectives (9 key goals)
  - Input sources and formats
  - End-to-end architecture diagram
  - All 15+ system components
  - Technology stack
  - Development order
  - Success metrics

---

### Project Planning Documents

**[Plan.md](Plan.md)** - 550+ lines
- **Purpose:** Detailed 16-week development plan
- **Contains:** Phased breakdown, deliverables, acceptance criteria
- **Audience:** Project managers, development team
- **Update Frequency:** Weekly
- **Key Sections:**
  - Timeline overview
  - Phase 1-6 details (goals, deliverables, acceptance criteria)
  - Testing strategy
  - Risk management
  - Resource requirements

**[Tasks.md](Tasks.md)** - 650+ lines
- **Purpose:** Actionable task tracking with 200+ items
- **Contains:** Detailed tasks, status, dependencies
- **Audience:** Development team, project managers
- **Update Frequency:** Daily/Weekly
- **Key Sections:**
  - Task status legend
  - Phase-by-phase task breakdown
  - Cross-phase activities
  - Statistics and metrics
  - Progress tracking

---

### User & Developer Guides

**[README.md](README.md)** - 250+ lines
- **Purpose:** Quick project overview and getting started
- **Contains:** Project purpose, quick start, structure overview, roadmap
- **Audience:** Everyone
- **Key Sections:**
  - Overview and philosophy
  - Quick start instructions
  - Project structure
  - Development roadmap
  - Key features
  - Testing instructions
  - Code standards
  - Performance targets

**[GETTING_STARTED.md](GETTING_STARTED.md)** - 350+ lines
- **Purpose:** Comprehensive development setup guide
- **Contains:** Installation, configuration, common tasks, troubleshooting
- **Audience:** Developers setting up the project
- **Key Sections:**
  - Prerequisites
  - Installation steps
  - Running tests
  - Code quality tools
  - Working with data
  - Common tasks
  - Troubleshooting
  - Workflow examples

---

### Status & Summary Documents

**[DEVELOPMENT_STATUS.md](DEVELOPMENT_STATUS.md)** - 400+ lines
- **Purpose:** Current system status and progress dashboard
- **Contains:** Component status, metrics, risk assessment, deployment readiness
- **Audience:** Project managers, stakeholders, team leads
- **Update Frequency:** Weekly
- **Key Sections:**
  - Executive summary
  - Completed deliverables
  - Current component status
  - Code quality metrics
  - Performance baselines
  - Risk assessment
  - Deployment readiness
  - Success criteria

**[WEEK1_SUMMARY.md](WEEK1_SUMMARY.md)** - 300+ lines
- **Purpose:** Summary of Week 1 accomplishments
- **Contains:** What was built, metrics, validation, lessons learned
- **Audience:** Everyone
- **Key Sections:**
  - Overview of Week 1
  - What was built (6 major areas)
  - Metrics and statistics
  - Testing results
  - Architecture established
  - Validation against requirements
  - Knowledge transfer items

---

## 📂 Source Code Organization

### Core Data Models
**[src/models/incident.py](src/models/incident.py)** - 316 lines
- PatientInfo, SurgeryInfo, IncidentDetails, AnesthesiaTechnique
- MedicationError, OutcomeInfo, ContextMetadata, Incident
- Pydantic validation for all models
- Complete with docstrings and examples

**[src/models/analysis.py](src/models/analysis.py)** - 198 lines
- AIAnalysis (AI output model)
- Theme (clustering results)
- VectorMetadata (vector store metadata)

### Data Ingestion
**[src/ingestion/excel_parser.py](src/ingestion/excel_parser.py)** - 392 lines
- ExcelParser class
- Support for .xlsx, .xls, .csv formats
- Column mapping with fallbacks
- Missing value and whitespace handling
- Schema validation

### Utilities
**[src/utils/logger.py](src/utils/logger.py)** - 65 lines
- Structured logging configuration
- Console and file handlers

**[src/utils/config.py](src/utils/config.py)** - 68 lines
- Settings management using Pydantic
- Environment variable configuration

**[src/utils/helpers.py](src/utils/helpers.py)** - 74 lines
- Utility functions (ID generation, normalization, chunking, flattening)

---

## 🧪 Test Files

### Test Fixtures
**[tests/fixtures/sample_incidents.py](tests/fixtures/sample_incidents.py)** - 260 lines
- 5 comprehensive fixtures for testing
- Sample incident, analysis, dataframe, theme, metadata

### Unit Tests
**[tests/unit/test_models.py](tests/unit/test_models.py)** - 350 lines
- 27 test cases for data models
- Tests for all 10 model types
- Validation and edge case coverage

**[tests/unit/test_parsers.py](tests/unit/test_parsers.py)** - 410 lines
- 35+ test cases for Excel parser
- Column retrieval, numeric handling, row/dataframe parsing
- File validation and edge cases
- Integration tests

---

## ⚙️ Configuration Files

### Package Configuration
- **[pyproject.toml](pyproject.toml)** - Poetry dependencies and configuration
- **[conftest.py](conftest.py)** - Pytest configuration

### Environment
- **[.env](/.env)** - Development environment variables
- **[.env.example](.env.example)** - Template for environment variables
- **[.gitignore](.gitignore)** - Git configuration

---

## 🔍 How to Use This Documentation

### I want to...

**Get started quickly**
→ Read [GETTING_STARTED.md](GETTING_STARTED.md)

**Understand the architecture**
→ Read [project_overview.md](project_overview.md)

**Check current progress**
→ Read [DEVELOPMENT_STATUS.md](DEVELOPMENT_STATUS.md)

**See what was built this week**
→ Read [WEEK1_SUMMARY.md](WEEK1_SUMMARY.md)

**Find a specific task**
→ Search [Tasks.md](Tasks.md)

**Plan the next phase**
→ Read [Plan.md](Plan.md) for Phase 2

**Look at code examples**
→ Check [tests/unit/test_models.py](tests/unit/test_models.py) or [tests/unit/test_parsers.py](tests/unit/test_parsers.py)

**Understand data models**
→ Review [src/models/incident.py](src/models/incident.py) and [src/models/analysis.py](src/models/analysis.py)

**Learn about the parser**
→ Study [src/ingestion/excel_parser.py](src/ingestion/excel_parser.py)

**Set up development environment**
→ Follow [README.md](README.md) then [GETTING_STARTED.md](GETTING_STARTED.md)

---

## 📊 Document Statistics

| Document | Lines | Focus | Audience |
|----------|-------|-------|----------|
| project_overview.md | 650+ | Architecture | Architects |
| Plan.md | 550+ | Schedule | Managers |
| Tasks.md | 650+ | Tracking | Team |
| README.md | 250+ | Overview | Everyone |
| GETTING_STARTED.md | 350+ | Setup | Developers |
| DEVELOPMENT_STATUS.md | 400+ | Status | Managers |
| WEEK1_SUMMARY.md | 300+ | Results | Everyone |
| **Total** | **3,100+** | **Complete** | **All** |

---

## 🎓 Learning Path

### For New Developers (1-2 hours)
1. Read README.md (5 min)
2. Read GETTING_STARTED.md (10 min)
3. Set up environment (20 min)
4. Run tests (5 min)
5. Review src/models/incident.py (10 min)
6. Check tests/unit/test_models.py (15 min)

### For Project Managers (30 minutes)
1. Read README.md (5 min)
2. Read DEVELOPMENT_STATUS.md (10 min)
3. Review Plan.md timeline (10 min)
4. Check Tasks.md progress (5 min)

### For Architects (2-3 hours)
1. Read project_overview.md (30 min)
2. Study src/models/ (20 min)
3. Review src/ingestion/excel_parser.py (15 min)
4. Check tests/ structure (15 min)
5. Read Plan.md for future (20 min)

### For Team Leads (1 hour)
1. Read DEVELOPMENT_STATUS.md (10 min)
2. Check Tasks.md (10 min)
3. Review WEEK1_SUMMARY.md (10 min)
4. Skim project_overview.md (10 min)
5. Review Plan.md for Phase 2 (20 min)

---

## 📝 Document Maintenance

### Updated Weekly
- Tasks.md (task status changes)
- DEVELOPMENT_STATUS.md (component status)

### Updated Per Phase
- Plan.md (add details for next phase)
- project_overview.md (if architecture changes)

### Updated Per Release
- README.md (feature updates)
- DEVELOPMENT_STATUS.md (major milestone)

### Updated As Needed
- GETTING_STARTED.md (new features)
- Source code documentation (code changes)

---

## 🔗 Quick Links by Role

### Developer
- [GETTING_STARTED.md](GETTING_STARTED.md) - Setup
- [src/models/](src/models/) - Data structures
- [tests/](tests/) - Examples and tests
- [pyproject.toml](pyproject.toml) - Dependencies

### Project Manager
- [DEVELOPMENT_STATUS.md](DEVELOPMENT_STATUS.md) - Status
- [Plan.md](Plan.md) - Schedule
- [Tasks.md](Tasks.md) - Details
- [WEEK1_SUMMARY.md](WEEK1_SUMMARY.md) - Results

### Architect
- [project_overview.md](project_overview.md) - Design
- [src/](src/) - Implementation
- [Plan.md](Plan.md) - Future architecture
- [DEVELOPMENT_STATUS.md](DEVELOPMENT_STATUS.md) - Status

### Team Lead
- [Tasks.md](Tasks.md) - Assignments
- [DEVELOPMENT_STATUS.md](DEVELOPMENT_STATUS.md) - Progress
- [Plan.md](Plan.md) - Timeline
- [project_overview.md](project_overview.md) - Technical context

---

## 🚀 Getting Help

**For setup issues:**
→ [GETTING_STARTED.md](GETTING_STARTED.md) Troubleshooting section

**For architecture questions:**
→ [project_overview.md](project_overview.md) relevant section

**For task clarification:**
→ [Tasks.md](Tasks.md) specific phase

**For project status:**
→ [DEVELOPMENT_STATUS.md](DEVELOPMENT_STATUS.md) relevant section

**For code examples:**
→ [tests/unit/](tests/unit/) test files

**For process questions:**
→ [Plan.md](Plan.md) methodology section

---

**Last Updated:** May 20, 2026  
**Total Documentation:** 32 files, 3,500+ lines

🎯 **Choose your starting point above and begin!**
