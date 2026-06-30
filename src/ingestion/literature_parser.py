"""Parser for clinical literature documents (guidelines, papers, protocols).

Supports three ingestion modes:
  1. ``parse_text()``       — plain text with explicit metadata kwargs
  2. ``parse_pdf()``        — PDF file via pdfplumber (no doubled-char fix needed)
  3. ``parse_json_batch()`` — list of dicts from a JSON feed or API response

All modes return ``LiteratureDocument`` objects that can be embedded and
stored in the same Qdrant collection as incident reports, distinguished by
``source_type = "literature" | "guideline" | "protocol"``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.models.literature import LiteratureDocument
from src.utils.logger import get_logger

logger = get_logger(__name__)

_VALID_SOURCE_TYPES = frozenset({"literature", "guideline", "protocol", "review"})


class LiteratureParser:
    """Parse clinical literature documents into LiteratureDocument objects.

    Usage::

        parser = LiteratureParser()

        # Plain text
        doc = parser.parse_text(
            title="Difficult Airway Society 2015 Guidelines",
            content="...",
            source_type="guideline",
            authors=["Frerk C", "Mitchell VS"],
            year=2015,
            doi="10.1093/bja/aev354",
            journal="British Journal of Anaesthesia",
        )

        # PDF
        docs = parser.parse_pdf(Path("ANZCA_airway_guidelines.pdf"))

        # JSON batch
        docs = parser.parse_json_batch([
            {"title": "...", "content": "...", "year": 2022},
            ...
        ])
    """

    # ── Public API ─────────────────────────────────────────────────────────────

    def parse_text(
        self,
        title: str,
        content: str,
        source_type: str = "literature",
        authors: list[str] | None = None,
        year: int | None = None,
        doi: str | None = None,
        journal: str | None = None,
        keywords: list[str] | None = None,
        **extra: Any,
    ) -> LiteratureDocument:
        """Create a LiteratureDocument from explicit text and metadata."""
        source_type = self._validate_source_type(source_type)
        if not title.strip():
            raise ValueError("title must not be empty")
        if not content.strip():
            raise ValueError("content must not be empty")

        doc = LiteratureDocument.create(
            title=title.strip(),
            content=content.strip(),
            source_type=source_type,
            authors=authors or [],
            year=year,
            doi=doi,
            journal=journal,
            keywords=keywords or self._extract_keywords(content),
            raw_data={"input_method": "text", **extra},
        )
        logger.info("LiteratureParser: created document '%s' (%s)", doc.title[:60], source_type)
        return doc

    def parse_pdf(
        self,
        path: Path,
        source_type: str = "literature",
        title: str | None = None,
        **metadata: Any,
    ) -> LiteratureDocument:
        """Extract text from a PDF and return a LiteratureDocument.

        The title defaults to the PDF filename stem when not provided.
        Unlike AIR Log PDFs, literature PDFs do NOT have the doubled-character
        encoding artefact — plain pdfplumber extraction is used directly.
        """
        try:
            import pdfplumber
        except ImportError as exc:
            raise RuntimeError(
                "pdfplumber is required: poetry add pdfplumber"
            ) from exc

        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {path}")
        if path.suffix.lower() != ".pdf":
            raise ValueError(f"Expected .pdf, got: {path.suffix!r}")

        source_type = self._validate_source_type(source_type)

        try:
            with pdfplumber.open(path) as pdf:
                pages_text = [page.extract_text() or "" for page in pdf.pages]
            full_text = "\n".join(pages_text).strip()
        except Exception as exc:
            raise RuntimeError(f"Failed to extract PDF text: {exc}") from exc

        if not full_text:
            raise ValueError(f"No text could be extracted from {path.name}")

        resolved_title = title or path.stem.replace("_", " ").replace("-", " ")

        doc = LiteratureDocument.create(
            title=resolved_title,
            content=full_text,
            source_type=source_type,
            keywords=self._extract_keywords(full_text),
            raw_data={
                "input_method": "pdf",
                "source_file": path.name,
                "page_count": len(pages_text),
                **metadata,
            },
        )
        logger.info(
            "LiteratureParser: parsed PDF '%s' → '%s' (%d pages)",
            path.name,
            doc.title[:60],
            len(pages_text),
        )
        return doc

    def parse_json_batch(
        self,
        records: list[dict[str, Any]],
        default_source_type: str = "literature",
    ) -> list[LiteratureDocument]:
        """Parse a list of dicts into LiteratureDocument objects.

        Each dict must have at minimum ``"title"`` and ``"content"`` keys.
        Optional keys: ``source_type``, ``authors``, ``year``, ``doi``,
        ``journal``, ``keywords``.

        Malformed records are skipped with a warning rather than raising.
        """
        documents: list[LiteratureDocument] = []
        for i, record in enumerate(records):
            try:
                doc = self._parse_record(record, default_source_type)
                documents.append(doc)
            except (ValueError, KeyError) as exc:
                logger.warning(
                    "LiteratureParser: skipping record %d — %s", i, exc
                )
        logger.info(
            "LiteratureParser: parsed %d/%d records", len(documents), len(records)
        )
        return documents

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _parse_record(
        self, record: dict[str, Any], default_source_type: str
    ) -> LiteratureDocument:
        title = str(record.get("title", "")).strip()
        content = str(record.get("content", record.get("abstract", ""))).strip()
        if not title:
            raise ValueError("record is missing 'title'")
        if not content:
            raise ValueError(f"record '{title[:40]}' is missing 'content' or 'abstract'")

        authors_raw = record.get("authors", [])
        authors = (
            [str(a) for a in authors_raw]
            if isinstance(authors_raw, list)
            else [str(authors_raw)]
        )

        year_raw = record.get("year")
        try:
            year = int(year_raw) if year_raw is not None else None
        except (ValueError, TypeError):
            year = None

        source_type = self._validate_source_type(
            record.get("source_type", default_source_type)
        )

        return LiteratureDocument.create(
            title=title,
            content=content,
            source_type=source_type,
            authors=authors,
            year=year,
            doi=record.get("doi"),
            journal=record.get("journal"),
            keywords=record.get("keywords") or self._extract_keywords(content),
            raw_data={"input_method": "json", **{
                k: v for k, v in record.items()
                if k not in ("title", "content", "abstract", "authors", "year",
                             "doi", "journal", "keywords", "source_type")
            }},
        )

    @staticmethod
    def _validate_source_type(source_type: str) -> str:
        st = source_type.lower().strip()
        if st not in _VALID_SOURCE_TYPES:
            logger.warning(
                "Unknown source_type '%s' — defaulting to 'literature'", source_type
            )
            return "literature"
        return st

    @staticmethod
    def _extract_keywords(text: str, max_keywords: int = 10) -> list[str]:
        """Heuristic keyword extraction from text (no NLP dependency).

        Finds capitalised multi-word phrases and domain terms.
        Used as a fallback when no explicit keywords are provided.
        """
        # Clinical domain terms to look for
        _DOMAIN_TERMS = [
            "airway management", "difficult intubation", "laryngoscopy",
            "anaesthesia", "anesthesia", "patient safety", "clinical governance",
            "root cause analysis", "incident reporting", "medication error",
            "surgical checklist", "WHO checklist", "postoperative", "perioperative",
            "complication", "morbidity", "mortality", "resuscitation",
            "capnography", "pulse oximetry", "monitoring", "guideline",
            "protocol", "checklist", "simulation", "training",
        ]
        found: list[str] = []
        text_lower = text.lower()
        for term in _DOMAIN_TERMS:
            if term in text_lower and term not in found:
                found.append(term)
            if len(found) >= max_keywords:
                break
        return found
