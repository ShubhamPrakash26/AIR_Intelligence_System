"""Unit tests for Week 13: Multi-Source RAG.

Covers:
  - LiteratureDocument model (creation, embeddable_text, citation_string)
  - LiteratureParser (text, JSON batch, error handling, keyword extraction)
  - extract_literature_metadata() VectorMetadata mapping
  - SearchFilters.source_type filter + to_qdrant_filter()
  - VectorMetadata backward-compatibility (new fields have defaults)

No real PDF, network, or LLM calls.
"""

from __future__ import annotations

import pytest

from src.ingestion.literature_parser import LiteratureParser
from src.models.literature import LiteratureDocument


# ---------------------------------------------------------------------------
# LiteratureDocument — model
# ---------------------------------------------------------------------------


class TestLiteratureDocument:
    def test_create_assigns_uuid(self):
        import uuid
        doc = LiteratureDocument.create(title="Test", content="Body text here.")
        uuid.UUID(doc.document_id)

    def test_create_sets_title_and_content(self):
        doc = LiteratureDocument.create(title="My Title", content="My content.")
        assert doc.title == "My Title"
        assert doc.content == "My content."

    def test_create_default_source_type_is_literature(self):
        doc = LiteratureDocument.create(title="T", content="C")
        assert doc.source_type == "literature"

    def test_create_custom_source_type(self):
        doc = LiteratureDocument.create(title="T", content="C", source_type="guideline")
        assert doc.source_type == "guideline"

    def test_embeddable_text_includes_title(self):
        doc = LiteratureDocument.create(title="Airway Guidelines", content="Content here.")
        assert "Airway Guidelines" in doc.embeddable_text

    def test_embeddable_text_includes_content(self):
        doc = LiteratureDocument.create(title="T", content="Unique content body.")
        assert "Unique content body." in doc.embeddable_text

    def test_embeddable_text_includes_keywords(self):
        doc = LiteratureDocument.create(
            title="T", content="C", keywords=["airway", "safety"]
        )
        assert "airway" in doc.embeddable_text
        assert "safety" in doc.embeddable_text

    def test_citation_string_with_full_metadata(self):
        doc = LiteratureDocument.create(
            title="Major Airway Complications",
            content="C",
            authors=["Cook TM", "Woodall N"],
            year=2011,
            journal="Br J Anaesth",
            doi="10.1093/bja/aer058",
        )
        cs = doc.citation_string
        assert "Cook TM" in cs
        assert "2011" in cs
        assert "Major Airway Complications" in cs

    def test_citation_string_truncates_authors_at_3(self):
        doc = LiteratureDocument.create(
            title="T",
            content="C",
            authors=["A", "B", "C", "D", "E"],
            year=2020,
        )
        assert "et al." in doc.citation_string

    def test_citation_string_no_authors(self):
        doc = LiteratureDocument.create(title="Guidelines", content="C", year=2021)
        cs = doc.citation_string
        assert "Guidelines" in cs

    def test_document_id_unique_per_instance(self):
        d1 = LiteratureDocument.create(title="T", content="C")
        d2 = LiteratureDocument.create(title="T", content="C")
        assert d1.document_id != d2.document_id


# ---------------------------------------------------------------------------
# LiteratureParser — parse_text
# ---------------------------------------------------------------------------


class TestLiteratureParserText:
    def _parser(self) -> LiteratureParser:
        return LiteratureParser()

    def test_parse_text_returns_document(self):
        doc = self._parser().parse_text(title="T", content="Body text.")
        assert isinstance(doc, LiteratureDocument)

    def test_parse_text_title_preserved(self):
        doc = self._parser().parse_text(title="Airway Guidelines 2015", content="Content.")
        assert doc.title == "Airway Guidelines 2015"

    def test_parse_text_content_preserved(self):
        doc = self._parser().parse_text(title="T", content="Specific body content.")
        assert doc.content == "Specific body content."

    def test_parse_text_default_source_type(self):
        doc = self._parser().parse_text(title="T", content="C")
        assert doc.source_type == "literature"

    def test_parse_text_guideline_source_type(self):
        doc = self._parser().parse_text(title="T", content="C", source_type="guideline")
        assert doc.source_type == "guideline"

    def test_parse_text_protocol_source_type(self):
        doc = self._parser().parse_text(title="T", content="C", source_type="protocol")
        assert doc.source_type == "protocol"

    def test_parse_text_unknown_source_type_defaults_to_literature(self):
        doc = self._parser().parse_text(title="T", content="C", source_type="unknown_xyz")
        assert doc.source_type == "literature"

    def test_parse_text_authors_stored(self):
        doc = self._parser().parse_text(
            title="T", content="C", authors=["Cook TM", "Woodall N"]
        )
        assert doc.authors == ["Cook TM", "Woodall N"]

    def test_parse_text_year_stored(self):
        doc = self._parser().parse_text(title="T", content="C", year=2015)
        assert doc.year == 2015

    def test_parse_text_doi_stored(self):
        doc = self._parser().parse_text(title="T", content="C", doi="10.1093/bja/x")
        assert doc.doi == "10.1093/bja/x"

    def test_parse_text_empty_title_raises(self):
        with pytest.raises(ValueError, match="title"):
            self._parser().parse_text(title="", content="Content.")

    def test_parse_text_empty_content_raises(self):
        with pytest.raises(ValueError, match="content"):
            self._parser().parse_text(title="Title", content="")

    def test_parse_text_keywords_auto_extracted(self):
        doc = self._parser().parse_text(
            title="Difficult Airway Management",
            content="airway management and patient safety guidelines for anaesthesia",
        )
        assert isinstance(doc.keywords, list)


# ---------------------------------------------------------------------------
# LiteratureParser — parse_json_batch
# ---------------------------------------------------------------------------


class TestLiteratureParserJsonBatch:
    def _parser(self) -> LiteratureParser:
        return LiteratureParser()

    def _records(self) -> list[dict]:
        return [
            {
                "title": "NAP4 Airway Report",
                "content": "Major complications of airway management in the UK.",
                "authors": ["Cook TM", "Woodall N"],
                "year": 2011,
                "doi": "10.1093/bja/aer058",
                "journal": "Br J Anaesth",
                "source_type": "literature",
            },
            {
                "title": "DAS Guidelines 2015",
                "abstract": "Difficult Airway Society 2015 guidelines for management.",
                "authors": ["Frerk C"],
                "year": 2015,
                "source_type": "guideline",
            },
        ]

    def test_batch_returns_list(self):
        result = self._parser().parse_json_batch(self._records())
        assert isinstance(result, list)

    def test_batch_correct_count(self):
        result = self._parser().parse_json_batch(self._records())
        assert len(result) == 2

    def test_batch_first_doc_title(self):
        docs = self._parser().parse_json_batch(self._records())
        assert docs[0].title == "NAP4 Airway Report"

    def test_batch_abstract_used_as_content(self):
        docs = self._parser().parse_json_batch(self._records())
        assert "Difficult Airway Society" in docs[1].content

    def test_batch_source_types_preserved(self):
        docs = self._parser().parse_json_batch(self._records())
        assert docs[0].source_type == "literature"
        assert docs[1].source_type == "guideline"

    def test_batch_year_preserved(self):
        docs = self._parser().parse_json_batch(self._records())
        assert docs[0].year == 2011

    def test_batch_skips_missing_title(self):
        records = [
            {"content": "Content without title."},
            {"title": "Valid", "content": "Content."},
        ]
        docs = self._parser().parse_json_batch(records)
        assert len(docs) == 1
        assert docs[0].title == "Valid"

    def test_batch_skips_missing_content(self):
        records = [
            {"title": "No content here"},
            {"title": "Valid", "content": "Content."},
        ]
        docs = self._parser().parse_json_batch(records)
        assert len(docs) == 1

    def test_batch_empty_list_returns_empty(self):
        assert self._parser().parse_json_batch([]) == []

    def test_batch_default_source_type_applied(self):
        records = [{"title": "T", "content": "C"}]
        docs = self._parser().parse_json_batch(records, default_source_type="protocol")
        assert docs[0].source_type == "protocol"

    def test_batch_invalid_year_becomes_none(self):
        records = [{"title": "T", "content": "C", "year": "not-a-year"}]
        docs = self._parser().parse_json_batch(records)
        assert docs[0].year is None


# ---------------------------------------------------------------------------
# extract_literature_metadata
# ---------------------------------------------------------------------------


class TestExtractLiteratureMetadata:
    def _doc(self, **kwargs) -> LiteratureDocument:
        return LiteratureDocument.create(
            title="NAP4 Airway Report",
            content="Abstract content describing major airway complications.",
            source_type="literature",
            authors=["Cook TM"],
            year=2011,
            journal="Br J Anaesth",
            **kwargs,
        )

    def test_returns_vector_metadata(self):
        from src.models.analysis import VectorMetadata
        from src.vector_store.metadata import extract_literature_metadata
        meta = extract_literature_metadata(self._doc())
        assert isinstance(meta, VectorMetadata)

    def test_incident_id_is_document_id(self):
        from src.vector_store.metadata import extract_literature_metadata
        doc = self._doc()
        meta = extract_literature_metadata(doc)
        assert meta.incident_id == doc.document_id

    def test_source_type_preserved(self):
        from src.vector_store.metadata import extract_literature_metadata
        meta = extract_literature_metadata(self._doc())
        assert meta.source_type == "literature"

    def test_guideline_source_type(self):
        from src.vector_store.metadata import extract_literature_metadata
        doc = LiteratureDocument.create(title="T", content="C", source_type="guideline")
        meta = extract_literature_metadata(doc)
        assert meta.source_type == "guideline"

    def test_severity_is_reference(self):
        from src.vector_store.metadata import extract_literature_metadata
        meta = extract_literature_metadata(self._doc())
        assert meta.severity == "Reference"

    def test_surgery_type_is_literature(self):
        from src.vector_store.metadata import extract_literature_metadata
        meta = extract_literature_metadata(self._doc())
        assert meta.surgery_type == "Literature"

    def test_title_stored(self):
        from src.vector_store.metadata import extract_literature_metadata
        meta = extract_literature_metadata(self._doc())
        assert meta.title == "NAP4 Airway Report"

    def test_year_stored(self):
        from src.vector_store.metadata import extract_literature_metadata
        meta = extract_literature_metadata(self._doc())
        assert meta.year == 2011

    def test_root_cause_is_content_excerpt(self):
        from src.vector_store.metadata import extract_literature_metadata
        meta = extract_literature_metadata(self._doc())
        assert "Abstract content" in meta.root_cause

    def test_key_learning_is_citation_string(self):
        from src.vector_store.metadata import extract_literature_metadata
        meta = extract_literature_metadata(self._doc())
        assert "Cook TM" in meta.key_learning

    def test_doi_used_as_source(self):
        from src.vector_store.metadata import extract_literature_metadata
        doc = self._doc(doi="10.1093/bja/aer058")
        meta = extract_literature_metadata(doc)
        assert meta.source == "10.1093/bja/aer058"


# ---------------------------------------------------------------------------
# SearchFilters — source_type extension
# ---------------------------------------------------------------------------


class TestSearchFiltersSourceType:
    def _filters(self, **kwargs):
        from src.retrieval.similarity_search import SearchFilters
        return SearchFilters(**kwargs)

    def test_default_source_type_is_none(self):
        f = self._filters()
        assert f.source_type is None

    def test_source_type_set(self):
        f = self._filters(source_type="incident_report")
        assert f.source_type == "incident_report"

    def test_is_empty_without_source_type(self):
        f = self._filters()
        assert f.is_empty()

    def test_is_not_empty_with_source_type(self):
        f = self._filters(source_type="literature")
        assert not f.is_empty()

    def test_to_qdrant_filter_with_source_type(self):
        f = self._filters(source_type="guideline")
        qf = f.to_qdrant_filter()
        assert qf is not None

    def test_to_qdrant_filter_none_when_empty(self):
        f = self._filters()
        assert f.to_qdrant_filter() is None

    def test_combined_filters_include_source_type(self):
        f = self._filters(severity="High", source_type="incident_report")
        qf = f.to_qdrant_filter()
        assert qf is not None
        # Both conditions should be in the filter
        assert len(qf.must) == 2


# ---------------------------------------------------------------------------
# VectorMetadata — backward-compatibility
# ---------------------------------------------------------------------------


class TestVectorMetadataBackwardCompat:
    def test_existing_fields_unchanged(self):
        from src.models.analysis import VectorMetadata
        meta = VectorMetadata(
            incident_id="abc",
            incident_type=["Airway Event"],
            severity="High",
            severity_score=0.9,
            surgery_type="Gynecology",
            root_cause="Root cause text",
            source="test.xlsx",
            timestamp="2026-01-01T00:00:00+00:00",
        )
        assert meta.incident_id == "abc"
        assert meta.severity == "High"

    def test_source_type_defaults_to_incident_report(self):
        from src.models.analysis import VectorMetadata
        meta = VectorMetadata(
            incident_id="abc",
            incident_type=[],
            severity="Low",
            severity_score=0.1,
            surgery_type="General",
            root_cause="",
            source="x",
            timestamp="2026-01-01T00:00:00+00:00",
        )
        assert meta.source_type == "incident_report"

    def test_title_defaults_to_none(self):
        from src.models.analysis import VectorMetadata
        meta = VectorMetadata(
            incident_id="abc",
            incident_type=[],
            severity="Low",
            severity_score=0.1,
            surgery_type="General",
            root_cause="",
            source="x",
            timestamp="2026-01-01T00:00:00+00:00",
        )
        assert meta.title is None
